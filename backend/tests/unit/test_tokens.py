"""JWT issuing and verification.

The negative cases are the point. A token library that accepts a token it
should reject is a full authentication bypass, and every rejection here
corresponds to a documented JWT attack.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.errors import TokenExpiredError, TokenInvalidError
from app.core.security.tokens import TokenService, TokenType

pytestmark = pytest.mark.unit

NOW = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)


@pytest.fixture
def issued(token_service: TokenService, user_id: uuid.UUID) -> tuple[str, uuid.UUID]:
    session_id = uuid.uuid4()
    token, _ = token_service.issue_access_token(
        subject=user_id, session_id=session_id, roles={"traveler"}, now=datetime.now(UTC)
    )
    return token, session_id


class TestAccessTokens:
    def test_roundtrip_preserves_claims(
        self, token_service: TokenService, issued: tuple[str, uuid.UUID], user_id: uuid.UUID
    ) -> None:
        token, session_id = issued
        claims = token_service.verify_access_token(token)
        assert claims.subject == user_id
        assert claims.session_id == session_id
        assert claims.roles == frozenset({"traveler"})

    def test_vendor_scope_is_carried(self, token_service: TokenService, user_id: uuid.UUID) -> None:
        vendor = uuid.uuid4()
        token, _ = token_service.issue_access_token(
            subject=user_id,
            session_id=uuid.uuid4(),
            roles={"vendor"},
            now=datetime.now(UTC),
            vendor_id=vendor,
        )
        assert token_service.verify_access_token(token).vendor_id == vendor

    def test_each_token_has_a_unique_jti(
        self, token_service: TokenService, user_id: uuid.UUID
    ) -> None:
        kwargs = {
            "subject": user_id,
            "session_id": uuid.uuid4(),
            "roles": set(),
            "now": datetime.now(UTC),
        }
        a, _ = token_service.issue_access_token(**kwargs)  # type: ignore[arg-type]
        b, _ = token_service.issue_access_token(**kwargs)  # type: ignore[arg-type]
        assert (
            token_service.verify_access_token(a).token_id
            != token_service.verify_access_token(b).token_id
        )

    def test_header_carries_kid_for_rotation(
        self, token_service: TokenService, issued: tuple[str, uuid.UUID]
    ) -> None:
        # Without kid, rotating the signing key means invalidating every live
        # session at once.
        assert jwt.get_unverified_header(issued[0])["kid"] is not None


class TestRejection:
    def test_expired_token_is_distinguishable(
        self, token_service: TokenService, user_id: uuid.UUID
    ) -> None:
        # Clients refresh on TOKEN_EXPIRED and sign out on TOKEN_INVALID, so
        # conflating the two either logs users out constantly or loops forever.
        long_past = datetime.now(UTC) - timedelta(hours=2)
        token, _ = token_service.issue_access_token(
            subject=user_id, session_id=uuid.uuid4(), roles=set(), now=long_past
        )
        with pytest.raises(TokenExpiredError):
            token_service.verify_access_token(token)

    def test_tampered_payload_is_rejected(
        self, token_service: TokenService, issued: tuple[str, uuid.UUID]
    ) -> None:
        token, _ = issued
        header, payload, signature = token.split(".")
        with pytest.raises(TokenInvalidError):
            token_service.verify_access_token(f"{header}.{payload}x.{signature}")

    def test_alg_none_is_rejected(self, token_service: TokenService, user_id: uuid.UUID) -> None:
        """The canonical JWT attack: strip the signature and set alg=none."""
        forged = jwt.encode(
            {
                "sub": str(user_id),
                "typ": "access",
                "iss": "roaming-wandering",
                "aud": "roaming-wandering-api",
                "iat": int(NOW.timestamp()),
                "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            },
            key="",
            algorithm="none",
        )
        with pytest.raises(TokenInvalidError):
            token_service.verify_access_token(forged)

    def test_refresh_token_is_not_accepted_as_an_access_token(
        self, token_service: TokenService, user_id: uuid.UUID
    ) -> None:
        """Token-type confusion. Same key, same signature — only ``typ``
        separates a password-reset token from a session."""
        reset = token_service.issue_action_token(
            subject=user_id,
            token_type=TokenType.PASSWORD_RESET,
            now=datetime.now(UTC),
            ttl_seconds=900,
        )
        with pytest.raises(TokenInvalidError):
            token_service.verify_access_token(reset)

    def test_garbage_is_rejected(self, token_service: TokenService) -> None:
        with pytest.raises(TokenInvalidError):
            token_service.verify_access_token("not.a.token")


class TestRefreshTokens:
    def test_plaintext_is_never_the_stored_value(self, token_service: TokenService) -> None:
        # A database dump must not yield usable sessions.
        issued = token_service.issue_refresh_token(now=datetime.now(UTC))
        assert issued.token_hash != issued.plaintext
        assert issued.token_hash == TokenService.hash_refresh_token(issued.plaintext)

    def test_tokens_are_unique(self, token_service: TokenService) -> None:
        now = datetime.now(UTC)
        tokens = {token_service.issue_refresh_token(now=now).plaintext for _ in range(100)}
        assert len(tokens) == 100

    def test_family_id_is_carried_through_rotation(self, token_service: TokenService) -> None:
        # Reuse detection revokes the whole family, so rotation must preserve it.
        first = token_service.issue_refresh_token(now=datetime.now(UTC))
        rotated = token_service.issue_refresh_token(
            now=datetime.now(UTC), family_id=first.family_id
        )
        assert rotated.family_id == first.family_id
        assert rotated.token_id != first.token_id
