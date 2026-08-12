"""Google ID token verification.

Every check below closes a specific, published attack. None of them are
optional, and skipping any one of them makes the others pointless:

* **Signature against Google's JWKS.** Without it, anyone can hand us a JSON
  object claiming to be any Google user.
* **Issuer** must be ``accounts.google.com``. A token signed by a different
  Google product is not a sign-in assertion.
* **Audience** must be *our* client id. Google ID tokens are issued to
  thousands of applications; without this check, a token a user granted to
  *any other app* is a valid login here. This is the single most commonly
  missed check in OAuth integrations.
* **Expiry**, with minimal leeway.
* **``email_verified``** — enforced by the use case, because the decision it
  drives (link or refuse) is a business rule, not a protocol one.

The JWKS is cached and refreshed by ``kid``. Fetching it per login would put a
Google round trip on the sign-in path and rate-limit us at scale; never
refreshing would break every login the day Google rotates its keys.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Final

import jwt
from jwt import PyJWKClient, PyJWTError

from app.core.logging import get_logger
from app.modules.auth.application.ports import GoogleIdentity
from app.modules.auth.domain import errors

logger = get_logger(__name__)

GOOGLE_JWKS_URI: Final = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS: Final = frozenset({"accounts.google.com", "https://accounts.google.com"})
_LEEWAY_SECONDS: Final = 10
#: Google publishes a Cache-Control of a few hours; one hour keeps us well
#: inside any rotation window without hammering the endpoint.
_JWKS_TTL_SECONDS: Final = 3600


class GoogleIdentityVerifier:
    """Implements
    :class:`app.modules.auth.application.ports.GoogleIdentityProvider`."""

    def __init__(self, *, client_ids: list[str], jwks_uri: str = GOOGLE_JWKS_URI) -> None:
        if not client_ids:
            msg = "Google sign-in requires at least one client id"
            raise ValueError(msg)
        # A list, not a single value: the web, Android and iOS clients each
        # have their own id, and all three are legitimate audiences.
        self._client_ids = client_ids
        self._jwks_uri = jwks_uri
        self._jwk_client: PyJWKClient | None = None
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()

    async def _client(self) -> PyJWKClient:
        async with self._lock:
            expired = time.monotonic() - self._loaded_at > _JWKS_TTL_SECONDS
            if self._jwk_client is None or expired:
                # PyJWKClient does blocking HTTP internally, so it is
                # constructed off the event loop. Its own LRU keeps the fetch
                # to once per key rotation rather than once per token.
                self._jwk_client = await asyncio.to_thread(
                    PyJWKClient, self._jwks_uri, cache_keys=True, lifespan=_JWKS_TTL_SECONDS
                )
                self._loaded_at = time.monotonic()
            return self._jwk_client

    async def verify_id_token(self, id_token: str, *, nonce: str | None = None) -> GoogleIdentity:
        try:
            client = await self._client()
            signing_key = await asyncio.to_thread(client.get_signing_key_from_jwt, id_token)
            claims: dict[str, Any] = await asyncio.to_thread(
                jwt.decode,
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._client_ids,
                leeway=_LEEWAY_SECONDS,
                options={
                    "require": ["iss", "aud", "exp", "sub"],
                    "verify_signature": True,
                    "verify_aud": True,
                    "verify_exp": True,
                },
            )
        except PyJWTError as exc:
            # Opaque to the caller on purpose. "Bad audience" vs "bad
            # signature" tells an attacker which part of a forgery to fix.
            logger.warning("google_token_verification_failed", error=type(exc).__name__)
            raise errors.OAuthVerificationError from exc
        except Exception as exc:
            logger.error("google_jwks_unavailable", error=str(exc))
            raise errors.OAuthVerificationError from exc

        if claims.get("iss") not in GOOGLE_ISSUERS:
            logger.warning("google_token_bad_issuer", issuer=claims.get("iss"))
            raise errors.OAuthVerificationError

        if nonce is not None and claims.get("nonce") != nonce:
            # Replay protection for the web flow: the client generates a nonce
            # per attempt, so a captured token cannot be re-submitted later.
            logger.warning("google_token_nonce_mismatch")
            raise errors.OAuthVerificationError

        email = claims.get("email")
        if not email:
            # Possible when the client requested no email scope. There is no
            # identity to link without one.
            raise errors.OAuthVerificationError

        return GoogleIdentity(
            subject=str(claims["sub"]),
            email=str(email),
            # Google sends this as a real bool, but some client libraries
            # stringify it. Both are normalised rather than trusted.
            email_verified=_as_bool(claims.get("email_verified")),
            full_name=claims.get("name"),
            picture=claims.get("picture"),
            hosted_domain=claims.get("hd"),
        )


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"
