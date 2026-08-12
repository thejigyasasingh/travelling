"""Ports the auth use cases depend on.

Declared here, next to their consumers; implemented in
``app.modules.auth.infrastructure``. That inversion is what lets every use case
in this module be tested with small fakes and no containers — see
``tests/unit/auth/``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.auth.domain.entities import Session, User
from app.modules.auth.domain.value_objects import Email, PhoneNumber


class UserRepository(Protocol):
    async def get(self, user_id: uuid.UUID) -> User | None: ...

    async def get_by_email(self, email: Email) -> User | None:
        """Case-insensitive (the column is ``citext``)."""
        ...

    async def get_by_phone(self, phone: PhoneNumber) -> User | None: ...

    async def get_by_oauth(self, provider: str, provider_account_id: str) -> User | None: ...

    async def add(self, user: User) -> None: ...

    async def link_oauth(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
        provider_account_id: str,
        email: str | None,
        raw_profile: dict[str, object],
        now: datetime,
    ) -> None: ...


class SessionRepository(Protocol):
    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        """Looked up by hash, never by plaintext — the plaintext is not stored."""
        ...

    async def add(self, session: Session) -> None: ...

    async def revoke_family(self, family_id: uuid.UUID, *, now: datetime, reason: str) -> int:
        """Kill every token in a chain. Returns how many were revoked.

        The count is reported in the security event; a family with many live
        members means the theft went undetected for a while.
        """
        ...

    async def revoke_all_for_user(
        self,
        user_id: uuid.UUID,
        *,
        now: datetime,
        reason: str,
        except_session: uuid.UUID | None = None,
    ) -> int: ...

    async def list_active_for_user(self, user_id: uuid.UUID, *, now: datetime) -> list[Session]: ...

    async def get_for_user(self, session_id: uuid.UUID, user_id: uuid.UUID) -> Session | None:
        """Scoped by user so one caller cannot revoke another's session by id."""
        ...

    async def has_any_for_device(
        self, user_id: uuid.UUID, ip_hash: str | None, user_agent: str | None
    ) -> bool:
        """Drives the "new device" flag on the login event."""
        ...


class ActionTokenStore(Protocol):
    """Single-use tokens for email verification and password reset.

    Only the ``jti`` is recorded, never the token. Burning it on first use is
    what makes a link that gets forwarded, cached by a mail scanner, or
    replayed from browser history work exactly once.
    """

    async def is_spent(self, jti: uuid.UUID) -> bool: ...

    async def spend(
        self,
        *,
        jti: uuid.UUID,
        user_id: uuid.UUID,
        purpose: str,
        expires_at: datetime,
        now: datetime,
    ) -> bool:
        """Atomically mark spent. ``False`` means it was already used.

        Atomic because two concurrent clicks on the same reset link must not
        both succeed — the second would silently overwrite the first user's
        chosen password.
        """
        ...


@dataclass(frozen=True, slots=True)
class OtpChallenge:
    challenge_id: str
    expires_in_seconds: int
    resend_after_seconds: int
    #: Only populated outside production, so local and staging can complete an
    #: OTP flow without an SMS gateway. Guarded in the settings, not here.
    debug_code: str | None = None


class OtpService(Protocol):
    """Issue and verify one-time codes.

    Backed by Redis rather than Postgres: codes live for minutes, churn
    constantly, and losing one to a cache restart costs a resend rather than
    data.
    """

    async def issue(self, phone: PhoneNumber, *, purpose: str) -> OtpChallenge: ...

    async def verify(self, challenge_id: str, code: str) -> PhoneNumber:
        """Returns the phone the challenge was issued for.

        Returning it — rather than taking it as an argument — is what stops a
        caller from verifying a code against a *different* number than the one
        it was sent to.
        """
        ...


@dataclass(frozen=True, slots=True)
class GoogleIdentity:
    subject: str  # Google's stable user id ("sub")
    email: str
    email_verified: bool
    full_name: str | None
    picture: str | None
    hosted_domain: str | None


class GoogleIdentityProvider(Protocol):
    async def verify_id_token(self, id_token: str, *, nonce: str | None = None) -> GoogleIdentity:
        """Verify signature, issuer, audience and expiry against Google's JWKS."""
        ...


class PasswordHasherPort(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, stored_hash: str | None) -> bool: ...
    def needs_rehash(self, stored_hash: str) -> bool: ...
