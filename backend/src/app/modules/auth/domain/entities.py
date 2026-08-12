"""The User aggregate and its session.

Every authentication *rule* lives here — lockout thresholds, what suspension
means, when a session may rotate. None of it touches a database, a framework
or a clock it does not own, so the whole security model is testable in
milliseconds and is proved by the tests in ``tests/unit/auth/``.

The aggregate boundary: ``User`` owns its roles and its identity. Sessions are
a **separate aggregate** referenced by id, not children of ``User``. A user
with 400 devices would otherwise have to be loaded with 400 sessions to check
one password, and every login would write the whole collection. Refresh
rotation touches one session row and nothing else.

``User`` never sees a plaintext password. It stores a hash produced by the
application layer, which owns the hasher — a domain that could hash would need
argon2 imported into it, and the purity contract exists precisely to prevent
that.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final

from app.modules.auth.domain import errors
from app.modules.auth.domain.events import (
    AccountLocked,
    AccountSuspended,
    EmailVerified,
    LoginFailed,
    PasswordChanged,
    PhoneVerified,
    RolesChanged,
    UserLoggedIn,
    UserRegistered,
)
from app.modules.auth.domain.rbac import DEFAULT_ROLE, Permission, Role, has_permission
from app.modules.auth.domain.value_objects import Email, PhoneNumber
from app.shared.domain.entity import AggregateRoot

# ── lockout policy ────────────────────────────────────────────────────────
# Progressive, not a flat "5 strikes and you're out for an hour".
#
# A legitimate user who fumbles their password twice should feel nothing. An
# attacker running a dictionary should hit a wall that grows faster than they
# can wait. Locking hard on the 5th attempt punishes the honest user (who then
# calls support) roughly as much as the attacker (who just moves to the next
# account in their list).
LOCKOUT_THRESHOLD: Final = 5
LOCKOUT_DURATIONS: Final = (60, 300, 900, 3600, 86_400)  # 1m, 5m, 15m, 1h, 24h
MAX_LOCKOUT_SECONDS: Final = LOCKOUT_DURATIONS[-1]

#: Actions that re-prompt for the password if the session is older than this.
SENSITIVE_ACTION_MAX_AGE: Final = 300  # 5 minutes


class UserStatus(StrEnum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    #: User-initiated. Reversible by signing in again within the grace period,
    #: unlike deletion, which is not.
    DEACTIVATED = "deactivated"


class SignupMethod(StrEnum):
    PASSWORD = "password"  # noqa: S105 — a signup method, not a secret
    GOOGLE = "google"
    OTP = "otp"


class User(AggregateRoot):
    """Identity, credentials and authorisation for one person."""

    __slots__ = (
        "avatar_url",
        "email",
        "email_verified_at",
        "failed_login_attempts",
        "full_name",
        "last_login_at",
        "locale",
        "locked_until",
        "lockout_level",
        "password_changed_at",
        "password_hash",
        "phone",
        "phone_verified_at",
        "roles",
        "signup_method",
        "status",
        "suspension_reason",
        "timezone",
        "vendor_id",
    )

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        email: Email,
        password_hash: str | None = None,
        full_name: str | None = None,
        phone: PhoneNumber | None = None,
        status: UserStatus = UserStatus.PENDING_VERIFICATION,
        roles: frozenset[Role] = frozenset({DEFAULT_ROLE}),
        signup_method: SignupMethod = SignupMethod.PASSWORD,
        locale: str = "en-IN",
        timezone: str = "Asia/Kolkata",
        avatar_url: str | None = None,
        vendor_id: uuid.UUID | None = None,
        email_verified_at: datetime | None = None,
        phone_verified_at: datetime | None = None,
        password_changed_at: datetime | None = None,
        last_login_at: datetime | None = None,
        failed_login_attempts: int = 0,
        lockout_level: int = 0,
        locked_until: datetime | None = None,
        suspension_reason: str | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(entity_id, version)
        self.email = email
        self.password_hash = password_hash
        self.full_name = full_name
        self.phone = phone
        self.status = status
        self.roles = roles
        self.signup_method = signup_method
        self.locale = locale
        self.timezone = timezone
        self.avatar_url = avatar_url
        self.vendor_id = vendor_id
        self.email_verified_at = email_verified_at
        self.phone_verified_at = phone_verified_at
        self.password_changed_at = password_changed_at
        self.last_login_at = last_login_at
        self.failed_login_attempts = failed_login_attempts
        self.lockout_level = lockout_level
        self.locked_until = locked_until
        self.suspension_reason = suspension_reason

    # ── factories ─────────────────────────────────────────────────────────

    @classmethod
    def register(
        cls,
        *,
        email: Email,
        password_hash: str,
        now: datetime,
        full_name: str | None = None,
        locale: str = "en-IN",
    ) -> User:
        user = cls(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            locale=locale,
            status=UserStatus.PENDING_VERIFICATION,
            signup_method=SignupMethod.PASSWORD,
            password_changed_at=now,
        )
        user.record(
            UserRegistered(
                aggregate_id=user.id,
                email=str(email),
                full_name=full_name,
                signup_method=SignupMethod.PASSWORD.value,
                locale=locale,
            )
        )
        return user

    @classmethod
    def register_via_oauth(
        cls,
        *,
        email: Email,
        provider_email_verified: bool,
        full_name: str | None,
        avatar_url: str | None,
        now: datetime,
        locale: str = "en-IN",
    ) -> User:
        """No password hash at all — not an empty string.

        ``None`` makes "this account cannot sign in with a password" a fact the
        type system carries. A sentinel like ``""`` eventually gets compared
        against and matches.

        The address is trusted as verified only when Google says it is; see
        :class:`OAuthEmailUnverifiedError` for why that check is load-bearing.
        """
        user = cls(
            email=email,
            password_hash=None,
            full_name=full_name,
            avatar_url=avatar_url,
            locale=locale,
            signup_method=SignupMethod.GOOGLE,
            status=UserStatus.ACTIVE
            if provider_email_verified
            else UserStatus.PENDING_VERIFICATION,
            email_verified_at=now if provider_email_verified else None,
        )
        user.record(
            UserRegistered(
                aggregate_id=user.id,
                email=str(email),
                full_name=full_name,
                signup_method=SignupMethod.GOOGLE.value,
                locale=locale,
            )
        )
        return user

    @classmethod
    def register_via_phone(
        cls, *, phone: PhoneNumber, email: Email, now: datetime, locale: str = "en-IN"
    ) -> User:
        """OTP signup. The phone is verified (the code proved it); the
        placeholder email is not, and the user is prompted to supply a real one
        before booking."""
        user = cls(
            email=email,
            password_hash=None,
            phone=phone,
            phone_verified_at=now,
            locale=locale,
            signup_method=SignupMethod.OTP,
            status=UserStatus.ACTIVE,
        )
        user.record(
            UserRegistered(
                aggregate_id=user.id,
                email=str(email),
                full_name=None,
                signup_method=SignupMethod.OTP.value,
                locale=locale,
            )
        )
        return user

    # ── state predicates ──────────────────────────────────────────────────

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_phone_verified(self) -> bool:
        return self.phone_verified_at is not None

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None

    @property
    def is_active(self) -> bool:
        return self.status in (UserStatus.ACTIVE, UserStatus.PENDING_VERIFICATION)

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and self.locked_until > now

    def lock_remaining_seconds(self, now: datetime) -> int:
        if not self.is_locked(now):
            return 0
        assert self.locked_until is not None
        return max(1, int((self.locked_until - now).total_seconds()))

    # ── authentication ────────────────────────────────────────────────────

    def assert_can_attempt_login(self, now: datetime) -> None:
        """Gate checked *before* the password is verified.

        Ordering matters: verifying first would burn 64 MiB of Argon2 work on
        an account that is locked anyway, which turns the lockout into an
        amplification vector rather than a defence.

        Suspension and deactivation both raise the generic credential error
        here — telling an unauthenticated caller "this account is suspended"
        confirms the account exists.
        """
        if self.status is UserStatus.SUSPENDED:
            raise errors.InvalidCredentialsError
        if self.status is UserStatus.DEACTIVATED:
            raise errors.InvalidCredentialsError
        if self.is_locked(now):
            raise errors.AccountLockedError(self.lock_remaining_seconds(now))

    def record_failed_login(self, now: datetime, *, ip_hash: str | None = None) -> None:
        """Count the failure and escalate the lockout if the threshold is hit.

        ``lockout_level`` is *not* reset by the lock expiring — only by a
        successful sign-in. Otherwise an attacker waits out each 60-second lock
        and gets five fresh attempts forever, and the escalation never bites.
        """
        self.failed_login_attempts += 1
        self.record(
            LoginFailed(
                aggregate_id=self.id,
                reason="invalid_password",
                attempt_number=self.failed_login_attempts,
                ip_hash=ip_hash,
            )
        )

        if self.failed_login_attempts < LOCKOUT_THRESHOLD:
            return

        duration = LOCKOUT_DURATIONS[min(self.lockout_level, len(LOCKOUT_DURATIONS) - 1)]
        self.locked_until = now + timedelta(seconds=duration)
        self.lockout_level += 1
        self.failed_login_attempts = 0  # next lock needs another full run
        self.record(
            AccountLocked(
                aggregate_id=self.id,
                email=str(self.email),
                locked_for_seconds=duration,
                failed_attempts=LOCKOUT_THRESHOLD,
            )
        )

    def record_successful_login(
        self,
        *,
        now: datetime,
        method: str,
        session_id: uuid.UUID,
        ip_hash: str | None = None,
        user_agent: str | None = None,
        is_new_device: bool = False,
    ) -> None:
        """Clears the whole lockout ladder.

        Proving knowledge of the password means the earlier failures were
        almost certainly typos, so the escalation resets completely rather than
        decaying.
        """
        self.failed_login_attempts = 0
        self.lockout_level = 0
        self.locked_until = None
        self.last_login_at = now

        if self.status is UserStatus.DEACTIVATED:
            self.status = UserStatus.ACTIVE  # signing in undoes a deactivation

        self.record(
            UserLoggedIn(
                aggregate_id=self.id,
                method=method,
                session_id=session_id,
                ip_hash=ip_hash,
                user_agent=user_agent,
                is_new_device=is_new_device,
            )
        )

    # ── verification ──────────────────────────────────────────────────────

    def verify_email(self, now: datetime) -> None:
        """Idempotent. A user who clicks the link twice, or whose mail client
        pre-fetches it, must see success rather than an error."""
        if self.is_email_verified:
            return
        self.email_verified_at = now
        if self.status is UserStatus.PENDING_VERIFICATION:
            self.status = UserStatus.ACTIVE
        self.record(EmailVerified(aggregate_id=self.id, email=str(self.email)))

    def verify_phone(self, phone: PhoneNumber, now: datetime) -> None:
        self.phone = phone
        self.phone_verified_at = now
        if self.status is UserStatus.PENDING_VERIFICATION:
            self.status = UserStatus.ACTIVE
        self.record(PhoneVerified(aggregate_id=self.id, phone_e164=str(phone)))

    def require_verified_email(self) -> None:
        """Called by booking and payout, not by sign-in — see
        :class:`EmailNotVerifiedError`."""
        if not self.is_email_verified:
            raise errors.EmailNotVerifiedError

    # ── password ──────────────────────────────────────────────────────────

    def set_password(
        self, new_hash: str, *, now: datetime, via_reset: bool, sessions_revoked: int = 0
    ) -> None:
        """Apply an already-hashed password.

        ``password_changed_at`` is the cutoff every outstanding reset token and
        refresh token is checked against, which is what makes "changing your
        password signs you out everywhere" true without hunting down rows one
        by one.
        """
        self.password_hash = new_hash
        self.password_changed_at = now
        # A password reset is the documented recovery path for a locked-out
        # user; leaving the lock in place would strand them.
        self.failed_login_attempts = 0
        self.lockout_level = 0
        self.locked_until = None
        self.record(
            PasswordChanged(
                aggregate_id=self.id,
                email=str(self.email),
                via_reset=via_reset,
                sessions_revoked=sessions_revoked,
            )
        )

    def assert_can_change_password(self) -> None:
        if not self.has_password:
            raise errors.PasswordNotSetError

    def credentials_issued_before(self, moment: datetime | None) -> bool:
        """True if a credential minted at ``moment`` predates the last password
        change and must therefore be rejected."""
        if moment is None or self.password_changed_at is None:
            return False
        return moment < self.password_changed_at

    # ── administration ────────────────────────────────────────────────────

    def suspend(self, *, reason: str, by: uuid.UUID | None, now: datetime) -> None:
        self.status = UserStatus.SUSPENDED
        self.suspension_reason = reason
        self.record(AccountSuspended(aggregate_id=self.id, reason=reason, suspended_by=by))

    def reinstate(self) -> None:
        self.status = (
            UserStatus.ACTIVE if self.is_email_verified else UserStatus.PENDING_VERIFICATION
        )
        self.suspension_reason = None

    def deactivate(self) -> None:
        self.status = UserStatus.DEACTIVATED

    # ── authorisation ─────────────────────────────────────────────────────

    def grant_roles(self, roles: frozenset[Role], *, by: uuid.UUID | None) -> None:
        granted = roles - self.roles
        if not granted:
            return
        self.roles = self.roles | granted
        self.record(
            RolesChanged(
                aggregate_id=self.id,
                granted=sorted(r.value for r in granted),
                revoked=[],
                changed_by=by,
            )
        )

    def revoke_roles(self, roles: frozenset[Role], *, by: uuid.UUID | None) -> None:
        """The default role cannot be removed.

        A user with no roles at all is a support ticket: they can sign in and
        then get a 403 on every single request, with nothing in the UI
        explaining why.
        """
        revoked = (roles & self.roles) - {DEFAULT_ROLE}
        if not revoked:
            return
        self.roles = self.roles - revoked
        self.record(
            RolesChanged(
                aggregate_id=self.id,
                granted=[],
                revoked=sorted(r.value for r in revoked),
                changed_by=by,
            )
        )

    @property
    def role_names(self) -> frozenset[str]:
        return frozenset(role.value for role in self.roles)

    def has_permission(self, *required: Permission) -> bool:
        return has_permission(self.role_names, *required)

    def require_permission(self, *required: Permission) -> None:
        if not self.has_permission(*required):
            raise errors.MissingPermissionError(*(p.value for p in required))


# ══════════════════════════════════════════════════════════════════════════
# Sessions
# ══════════════════════════════════════════════════════════════════════════


class Session(AggregateRoot):
    """One refresh token, and therefore one signed-in device.

    Chained by ``family_id``: rotating produces a new row whose ``parent_id``
    points at the one it replaced. The chain is what makes reuse detection
    possible — presenting a token that already has a successor means two
    parties hold the same credential, and only one of them is the legitimate
    client.
    """

    __slots__ = (
        "device_label",
        "expires_at",
        "family_id",
        "ip_hash",
        "issued_at",
        "last_used_at",
        "parent_id",
        "revoked_at",
        "revoked_reason",
        "rotated_at",
        "token_hash",
        "user_agent",
        "user_id",
    )

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        user_id: uuid.UUID,
        family_id: uuid.UUID,
        token_hash: str,
        issued_at: datetime,
        expires_at: datetime,
        parent_id: uuid.UUID | None = None,
        rotated_at: datetime | None = None,
        revoked_at: datetime | None = None,
        revoked_reason: str | None = None,
        last_used_at: datetime | None = None,
        ip_hash: str | None = None,
        user_agent: str | None = None,
        device_label: str | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(entity_id, version)
        self.user_id = user_id
        self.family_id = family_id
        self.token_hash = token_hash
        self.issued_at = issued_at
        self.expires_at = expires_at
        self.parent_id = parent_id
        self.rotated_at = rotated_at
        self.revoked_at = revoked_at
        self.revoked_reason = revoked_reason
        self.last_used_at = last_used_at
        self.ip_hash = ip_hash
        self.user_agent = user_agent
        self.device_label = device_label

    @classmethod
    def start(
        cls,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        family_id: uuid.UUID,
        issued_at: datetime,
        expires_at: datetime,
        ip_hash: str | None = None,
        user_agent: str | None = None,
        device_label: str | None = None,
    ) -> Session:
        return cls(
            user_id=user_id,
            family_id=family_id,
            token_hash=token_hash,
            issued_at=issued_at,
            expires_at=expires_at,
            ip_hash=ip_hash,
            user_agent=user_agent,
            device_label=device_label,
        )

    # ── state ─────────────────────────────────────────────────────────────

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_rotated(self) -> bool:
        return self.rotated_at is not None

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at <= now

    def assert_usable(self, now: datetime, *, grace_seconds: int) -> None:
        """Validate before rotating.

        The **grace window** is the subtle part. A mobile client rotates, the
        response is lost to a dropped connection, and it retries with the token
        it still has. That is indistinguishable from a replay by signature
        alone — so a token rotated within the last few seconds is treated as a
        lost response and the *same* successor is returned, while one rotated
        earlier is treated as theft and burns the family.

        Without the grace window every flaky mobile connection logs the user
        out and raises a false security alert.
        """
        if self.is_revoked:
            raise errors.SessionExpiredError
        if self.is_expired(now):
            raise errors.SessionExpiredError
        if self.is_rotated:
            assert self.rotated_at is not None
            if (now - self.rotated_at).total_seconds() <= grace_seconds:
                raise _WithinRotationGrace(self)
            raise errors.RefreshTokenReuseError(self.family_id)

    def rotate(
        self,
        *,
        new_token_hash: str,
        now: datetime,
        expires_at: datetime,
        ip_hash: str | None = None,
        user_agent: str | None = None,
    ) -> Session:
        """Mark this token spent and return its successor.

        The parent is kept, not deleted. A deleted parent cannot be recognised
        on replay — the lookup would simply miss and return "invalid token",
        and the theft would go undetected.
        """
        self.rotated_at = now
        self.last_used_at = now
        successor = Session(
            user_id=self.user_id,
            family_id=self.family_id,
            token_hash=new_token_hash,
            issued_at=now,
            expires_at=expires_at,
            parent_id=self.id,
            ip_hash=ip_hash or self.ip_hash,
            user_agent=user_agent or self.user_agent,
            device_label=self.device_label,
        )
        return successor

    def revoke(self, *, now: datetime, reason: str) -> None:
        if self.is_revoked:
            return
        self.revoked_at = now
        self.revoked_reason = reason


class _WithinRotationGrace(Exception):  # noqa: N818 — control flow, not an error surface
    """Internal signal: this token was rotated moments ago, so the client
    almost certainly lost the response. Caught by the refresh use case, which
    replays the successor. Never reaches the interface layer."""

    def __init__(self, session: Session) -> None:
        self.session = session
        super().__init__("token rotated within the grace window")


def utc(moment: datetime) -> datetime:
    """Guard against a naive datetime reaching a comparison.

    Naive vs aware comparison raises ``TypeError`` at runtime, and in this file
    that would mean a 500 on the login path rather than a wrong answer — but
    only for whichever branch happens to run.
    """
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
