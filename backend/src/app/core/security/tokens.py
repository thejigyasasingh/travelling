"""JWT issuing and verification.

**RS256, not HS256.** With a shared secret, every service that can *verify* a
token can also *forge* one. Asymmetric signing means the auth module holds the
private key and everything else — other modules today, other services
tomorrow, the mobile BFF, an internal admin tool — verifies with a public key
that is safe to distribute. That property is what makes the modular monolith
splittable later without a security redesign.

**Access tokens are stateless and short (15 min).** Checking a revocation list
on every request would put Redis in the hot path of every single call. The
window between "user revoked" and "token stops working" is bounded by the TTL
instead — the standard trade. High-impact actions (payouts, password change,
account deletion) additionally require a fresh re-authentication, so the
15-minute window is not a blank cheque.

**Refresh tokens are stateful, rotating, and reuse-detecting.** They live in
the database, one row per token, chained by ``family_id``. Presenting a token
that has already been rotated means the token was stolen (the legitimate
client would hold the newest one), so the entire family is revoked and the
user is forced to sign in again. That is the only reliable defence against a
stolen refresh token, and it is why refresh state is worth the lookup that
access tokens deliberately avoid.

``kid`` is in every header so keys can be rotated with an overlap window
rather than a flag day that logs out every user at once.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Final

import jwt
from jwt import PyJWTError

from app.core.config import SecuritySettings
from app.core.errors import TokenExpiredError, TokenInvalidError

_LEEWAY_SECONDS: Final = 10  # tolerate modest clock skew between pods
REFRESH_TOKEN_BYTES: Final = 32  # 256 bits of entropy


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    EMAIL_VERIFY = "email_verify"
    PASSWORD_RESET = "password_reset"  # noqa: S105 — a token type, not a secret


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Decoded, verified access token.

    Roles and the vendor scope are embedded so authorisation needs no database
    round-trip on the request path. The cost is staleness bounded by the token
    TTL: a role revoked now takes effect within 15 minutes. Where that is not
    acceptable — suspending a fraudulent vendor — the account-status check runs
    against the database on the affected endpoints.
    """

    subject: uuid.UUID
    session_id: uuid.UUID
    roles: frozenset[str]
    token_id: uuid.UUID
    issued_at: datetime
    expires_at: datetime
    vendor_id: uuid.UUID | None = None
    scopes: frozenset[str] = frozenset()
    #: Carried in the token so guards that need it cost no database read. The
    #: staleness window is one access-token TTL, and clients refresh right
    #: after verifying, so the user never sees a stale `false` for long.
    email_verified: bool = False

    def has_role(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))


@dataclass(frozen=True, slots=True)
class IssuedRefreshToken:
    """What the caller must persist vs. what it may return.

    ``plaintext`` goes to the client and is never stored. ``token_hash`` goes
    to the database. A leaked database dump therefore yields no usable session
    — the same reasoning as password hashing, applied to bearer credentials.
    """

    plaintext: str
    token_hash: str
    token_id: uuid.UUID
    family_id: uuid.UUID
    expires_at: datetime


class TokenService:
    """Stateless signer/verifier. Refresh-token *storage* is the auth module's
    repository; this class only mints and validates."""

    __slots__ = ("_algorithm", "_audience", "_issuer", "_kid", "_private", "_public", "_settings")

    def __init__(self, settings: SecuritySettings) -> None:
        if settings.jwt_private_key is None or settings.jwt_public_key is None:
            msg = "TokenService requires both a JWT private and public key"
            raise ValueError(msg)
        self._settings = settings
        self._private = settings.jwt_private_key.get_secret_value()
        self._public = settings.jwt_public_key.get_secret_value()
        self._algorithm = settings.jwt_algorithm
        self._issuer = settings.jwt_issuer
        self._audience = settings.jwt_audience
        self._kid = settings.jwt_key_id

    # ── access tokens ─────────────────────────────────────────────────────

    def issue_access_token(
        self,
        *,
        subject: uuid.UUID,
        session_id: uuid.UUID,
        roles: frozenset[str] | set[str],
        now: datetime,
        vendor_id: uuid.UUID | None = None,
        scopes: frozenset[str] | set[str] = frozenset(),
        email_verified: bool = False,
    ) -> tuple[str, datetime]:
        expires_at = now + timedelta(seconds=self._settings.access_token_ttl_seconds)
        claims: dict[str, Any] = {
            "iss": self._issuer,
            "aud": self._audience,
            "sub": str(subject),
            "sid": str(session_id),
            "jti": str(uuid.uuid4()),
            "typ": TokenType.ACCESS.value,
            "roles": sorted(roles),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "evf": email_verified,
        }
        if vendor_id is not None:
            claims["vid"] = str(vendor_id)
        if scopes:
            claims["scp"] = sorted(scopes)

        token = jwt.encode(
            claims, self._private, algorithm=self._algorithm, headers={"kid": self._kid}
        )
        return token, expires_at

    def verify_access_token(self, token: str) -> AccessTokenClaims:
        """Raises :class:`TokenExpiredError` / :class:`TokenInvalidError`.

        The two are distinguished because clients act differently: expired
        means "refresh silently", invalid means "sign in again".
        """
        payload = self._decode(token)

        if payload.get("typ") != TokenType.ACCESS.value:
            # Without this check a refresh or password-reset token would be
            # accepted as an access token — same signature, different purpose.
            raise TokenInvalidError("Token is not an access token")

        try:
            return AccessTokenClaims(
                subject=uuid.UUID(payload["sub"]),
                session_id=uuid.UUID(payload["sid"]),
                roles=frozenset(payload.get("roles", [])),
                token_id=uuid.UUID(payload["jti"]),
                issued_at=datetime.fromtimestamp(payload["iat"], tz=UTC),
                expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
                vendor_id=uuid.UUID(payload["vid"]) if payload.get("vid") else None,
                scopes=frozenset(payload.get("scp", [])),
                email_verified=bool(payload.get("evf", False)),
            )
        except (KeyError, ValueError) as exc:
            raise TokenInvalidError("Token claims are malformed") from exc

    # ── refresh tokens ────────────────────────────────────────────────────

    def issue_refresh_token(
        self, *, now: datetime, family_id: uuid.UUID | None = None
    ) -> IssuedRefreshToken:
        """Opaque random string, not a JWT.

        A refresh token is looked up in the database on every use anyway, so
        signing buys nothing and a JWT would leak its claims to anyone who
        reads the client's storage. 256 random bits are unguessable and carry
        no information.
        """
        plaintext = secrets.token_urlsafe(REFRESH_TOKEN_BYTES)
        return IssuedRefreshToken(
            plaintext=plaintext,
            token_hash=self.hash_refresh_token(plaintext),
            token_id=uuid.uuid4(),
            family_id=family_id or uuid.uuid4(),
            expires_at=now + timedelta(seconds=self._settings.refresh_token_ttl_seconds),
        )

    @staticmethod
    def hash_refresh_token(plaintext: str) -> str:
        """SHA-256, deliberately *not* Argon2.

        Argon2's cost exists to slow brute force against low-entropy human
        passwords. A 256-bit random token cannot be brute-forced, so the only
        job here is making a stolen database dump useless — and this lookup
        happens on every token refresh, where 64 MiB of memory per call would
        be a self-inflicted DoS.
        """
        return hashlib.sha256(plaintext.encode()).hexdigest()

    # ── single-use action tokens ──────────────────────────────────────────

    def issue_action_token(
        self,
        *,
        subject: uuid.UUID,
        token_type: TokenType,
        now: datetime,
        ttl_seconds: int,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Email verification and password reset.

        The ``jti`` is recorded by the caller and burned on use — a reset link
        forwarded, cached by a mail scanner, or replayed from browser history
        must work exactly once.
        """
        expires_at = now + timedelta(seconds=ttl_seconds)
        claims: dict[str, Any] = {
            "iss": self._issuer,
            "aud": self._audience,
            "sub": str(subject),
            "jti": str(uuid.uuid4()),
            "typ": token_type.value,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            **(extra or {}),
        }
        return jwt.encode(
            claims, self._private, algorithm=self._algorithm, headers={"kid": self._kid}
        )

    def verify_action_token(self, token: str, expected_type: TokenType) -> dict[str, Any]:
        payload = self._decode(token)
        if payload.get("typ") != expected_type.value:
            raise TokenInvalidError("Token is not valid for this action")
        return payload

    # ── internals ─────────────────────────────────────────────────────────

    def _decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self._public,
                algorithms=[self._algorithm],  # allowlist: blocks alg=none and HS256 confusion
                issuer=self._issuer,
                audience=self._audience,
                leeway=_LEEWAY_SECONDS,
                options={
                    "require": ["exp", "iat", "sub", "typ", "iss", "aud"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenExpiredError from exc
        except PyJWTError as exc:
            # Deliberately opaque to the client. "Bad audience" vs "bad
            # signature" tells an attacker which part of their forgery to fix.
            raise TokenInvalidError from exc


def constant_time_compare(a: str, b: str) -> bool:
    """For comparing secrets that arrive from a client (webhook signatures,
    API keys). ``==`` short-circuits on the first differing byte and leaks the
    matching prefix length through timing."""
    return secrets.compare_digest(a.encode(), b.encode())
