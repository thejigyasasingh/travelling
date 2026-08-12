"""In-memory doubles for the auth ports.

Small hand-written fakes, not mocks. A mock asserts that a method was called;
these behave like the real thing, which is what lets a test assert on the
*outcome* — "the family was revoked" — rather than on the interaction.

They are the reason every use-case test in this directory runs in milliseconds
with no containers, and the reason those tests keep passing when a repository
implementation changes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from app.modules.auth.application.ports import GoogleIdentity, OtpChallenge
from app.modules.auth.domain.entities import Session, User
from app.modules.auth.domain.value_objects import Email, PhoneNumber


class FakeUserRepository:
    def __init__(self, *users: User) -> None:
        self.users: dict[uuid.UUID, User] = {u.id: u for u in users}
        self.oauth_links: dict[tuple[str, str], uuid.UUID] = {}
        self.added: list[User] = []

    async def get(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)

    async def get_by_email(self, email: Email) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    async def get_by_phone(self, phone: PhoneNumber) -> User | None:
        return next((u for u in self.users.values() if u.phone == phone), None)

    async def get_by_oauth(self, provider: str, provider_account_id: str) -> User | None:
        user_id = self.oauth_links.get((provider, provider_account_id))
        return self.users.get(user_id) if user_id else None

    async def add(self, user: User) -> None:
        self.users[user.id] = user
        self.added.append(user)

    async def link_oauth(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
        provider_account_id: str,
        email: str | None,
        raw_profile: dict[str, object],
        now: datetime,
    ) -> None:
        self.oauth_links[(provider, provider_account_id)] = user_id

    def events(self) -> list[Any]:
        collected: list[Any] = []
        for user in self.users.values():
            collected.extend(user.pull_events())
        return collected


class FakeSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[uuid.UUID, Session] = {}
        self.known_devices: set[tuple[uuid.UUID, str | None, str | None]] = set()

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        return next((s for s in self.sessions.values() if s.token_hash == token_hash), None)

    async def get_for_user(self, session_id: uuid.UUID, user_id: uuid.UUID) -> Session | None:
        session = self.sessions.get(session_id)
        return session if session and session.user_id == user_id else None

    async def add(self, session: Session) -> None:
        self.sessions[session.id] = session

    async def revoke_family(self, family_id: uuid.UUID, *, now: datetime, reason: str) -> int:
        count = 0
        for session in self.sessions.values():
            if session.family_id == family_id and not session.is_revoked:
                session.revoke(now=now, reason=reason)
                count += 1
        return count

    async def revoke_all_for_user(
        self,
        user_id: uuid.UUID,
        *,
        now: datetime,
        reason: str,
        except_session: uuid.UUID | None = None,
    ) -> int:
        keep = self.sessions[except_session].family_id if except_session in self.sessions else None
        count = 0
        for session in self.sessions.values():
            if session.user_id != user_id or session.is_revoked:
                continue
            if keep is not None and session.family_id == keep:
                continue
            session.revoke(now=now, reason=reason)
            count += 1
        return count

    async def list_active_for_user(self, user_id: uuid.UUID, *, now: datetime) -> list[Session]:
        return [
            s
            for s in self.sessions.values()
            if s.user_id == user_id
            and not s.is_revoked
            and not s.is_rotated
            and not s.is_expired(now)
        ]

    async def has_any_for_device(
        self, user_id: uuid.UUID, ip_hash: str | None, user_agent: str | None
    ) -> bool:
        return (user_id, ip_hash, user_agent) in self.known_devices


class FakeActionTokenStore:
    """Mirrors the real store's atomic claim: the first spend wins."""

    def __init__(self) -> None:
        self.spent: set[uuid.UUID] = set()

    async def is_spent(self, jti: uuid.UUID) -> bool:
        return jti in self.spent

    async def spend(
        self,
        *,
        jti: uuid.UUID,
        user_id: uuid.UUID,
        purpose: str,
        expires_at: datetime,
        now: datetime,
    ) -> bool:
        if jti in self.spent:
            return False
        self.spent.add(jti)
        return True


class FakePasswordHasher:
    """Reversible "hash" so tests can assert on what was stored.

    Deliberately not Argon2: real hashing would add ~50 ms per call and turn a
    fast unit suite into a slow one, and none of these tests are about the KDF
    (test_tokens.py and the config tests cover that).
    """

    PREFIX = "hashed:"

    def __init__(self) -> None:
        self.dummy_verifications = 0

    def hash(self, password: str) -> str:
        return f"{self.PREFIX}{password}"

    def verify(self, password: str, stored_hash: str | None) -> bool:
        if stored_hash is None:
            # The real implementation burns equivalent CPU here; the fake just
            # records that it was asked, so a test can prove the timing-
            # equalisation path was taken.
            self.dummy_verifications += 1
            return False
        return stored_hash == f"{self.PREFIX}{password}"

    def needs_rehash(self, stored_hash: str) -> bool:
        return False


class FakeOtpService:
    def __init__(self) -> None:
        self.challenges: dict[str, tuple[PhoneNumber, str]] = {}
        self.issued: list[PhoneNumber] = []
        self.next_code = "482913"

    async def issue(self, phone: PhoneNumber, *, purpose: str) -> OtpChallenge:
        challenge_id = f"challenge-{len(self.challenges)}"
        self.challenges[challenge_id] = (phone, self.next_code)
        self.issued.append(phone)
        return OtpChallenge(
            challenge_id=challenge_id,
            expires_in_seconds=300,
            resend_after_seconds=60,
            debug_code=self.next_code,
        )

    async def verify(self, challenge_id: str, code: str) -> PhoneNumber:
        from app.modules.auth.domain import errors

        entry = self.challenges.get(challenge_id)
        if entry is None:
            raise errors.OtpInvalidError
        phone, expected = entry
        if code != expected:
            raise errors.OtpInvalidError(attempts_remaining=2)
        del self.challenges[challenge_id]  # single use
        return phone


class FakeGoogleProvider:
    def __init__(self, identity: GoogleIdentity | None = None) -> None:
        self.identity = identity or GoogleIdentity(
            subject="google-sub-123",
            email="priya@example.com",
            email_verified=True,
            full_name="Priya Sharma",
            picture="https://example.com/a.jpg",
            hosted_domain=None,
        )
        self.error: Exception | None = None

    async def verify_id_token(self, id_token: str, *, nonce: str | None = None) -> GoogleIdentity:
        if self.error is not None:
            raise self.error
        return self.identity


class FakeClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta
