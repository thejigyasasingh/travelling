"""Auth domain events.

These are how auth stays decoupled from everything that reacts to it. The auth
module does not import the notification, analytics or fraud modules; it records
facts and they subscribe.

Payloads carry **no secrets and no plaintext PII beyond what a consumer must
have to act**. An event travels through the outbox table, Redis, a Celery
worker and every log line along the way; a verification token in one would be
sitting in three systems in plaintext. So ``UserRegistered`` carries the user
id and the email — the notification consumer needs somewhere to send the mail —
but the token is minted by that consumer from a signed request, never shipped
inside the event.

Every ``event_type`` string is a permanent contract. A consumer deployed one
version behind, and an outbox row written five minutes ago, both still use it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

from app.shared.domain.events import DomainEvent

AGGREGATE = "user"


@dataclass(frozen=True, kw_only=True)
class UserRegistered(DomainEvent):
    """A new account exists. Not yet verified.

    Consumers: notification (verification email), analytics (signup funnel),
    CRM (lead), fraud (velocity check on the IP).
    """

    event_type: ClassVar[str] = "auth.user.registered"
    aggregate_type: ClassVar[str] = AGGREGATE

    email: str
    full_name: str | None
    signup_method: str  # password | google | otp
    locale: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.aggregate_id),
            "email": self.email,
            "full_name": self.full_name,
            "signup_method": self.signup_method,
            "locale": self.locale,
        }


@dataclass(frozen=True, kw_only=True)
class EmailVerificationRequested(DomainEvent):
    """Send (or resend) a verification link.

    Carries the token because the notification consumer has no way to mint
    one — it holds no signing key, and giving it one would widen the blast
    radius of a compromised worker far beyond what a 24-hour single-use link
    is worth. The trade is accepted deliberately: the token is short-lived,
    single-use, and the outbox row is purged after processing.
    """

    event_type: ClassVar[str] = "auth.email.verification_requested"
    aggregate_type: ClassVar[str] = AGGREGATE

    email: str
    token: str
    expires_in_seconds: int
    locale: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.aggregate_id),
            "email": self.email,
            "token": self.token,
            "expires_in_seconds": self.expires_in_seconds,
            "locale": self.locale,
        }


@dataclass(frozen=True, kw_only=True)
class EmailVerified(DomainEvent):
    event_type: ClassVar[str] = "auth.email.verified"
    aggregate_type: ClassVar[str] = AGGREGATE

    email: str

    def to_payload(self) -> dict[str, Any]:
        return {"user_id": str(self.aggregate_id), "email": self.email}


@dataclass(frozen=True, kw_only=True)
class PasswordResetRequested(DomainEvent):
    event_type: ClassVar[str] = "auth.password.reset_requested"
    aggregate_type: ClassVar[str] = AGGREGATE

    email: str
    token: str
    expires_in_seconds: int
    requested_ip_hash: str | None
    locale: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.aggregate_id),
            "email": self.email,
            "token": self.token,
            "expires_in_seconds": self.expires_in_seconds,
            "requested_ip_hash": self.requested_ip_hash,
            "locale": self.locale,
        }


@dataclass(frozen=True, kw_only=True)
class PasswordChanged(DomainEvent):
    """Covers both a reset and a deliberate change.

    Always triggers a "your password was changed" notification, including when
    the user did it themselves. That mail is the only signal an account-takeover
    victim gets, and it is worth the mild redundancy for the legitimate case.
    """

    event_type: ClassVar[str] = "auth.password.changed"
    aggregate_type: ClassVar[str] = AGGREGATE

    email: str
    via_reset: bool
    sessions_revoked: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.aggregate_id),
            "email": self.email,
            "via_reset": self.via_reset,
            "sessions_revoked": self.sessions_revoked,
        }


@dataclass(frozen=True, kw_only=True)
class UserLoggedIn(DomainEvent):
    """Successful sign-in. Drives new-device alerts and the fraud model.

    The IP is hashed. The raw address is personal data under GDPR and India's
    DPDP Act, and no consumer needs it — they need "is this the same client as
    last time?", which a stable hash answers.
    """

    event_type: ClassVar[str] = "auth.user.logged_in"
    aggregate_type: ClassVar[str] = AGGREGATE

    method: str  # password | google | otp | refresh
    session_id: uuid.UUID
    ip_hash: str | None
    user_agent: str | None
    is_new_device: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.aggregate_id),
            "method": self.method,
            "session_id": str(self.session_id),
            "ip_hash": self.ip_hash,
            "user_agent": self.user_agent,
            "is_new_device": self.is_new_device,
        }


@dataclass(frozen=True, kw_only=True)
class LoginFailed(DomainEvent):
    """Emitted per failed attempt, for the fraud model and for alerting on
    distributed credential stuffing that no single account's lockout counter
    would notice."""

    event_type: ClassVar[str] = "auth.login.failed"
    aggregate_type: ClassVar[str] = AGGREGATE

    reason: str
    attempt_number: int
    ip_hash: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.aggregate_id),
            "reason": self.reason,
            "attempt_number": self.attempt_number,
            "ip_hash": self.ip_hash,
        }


@dataclass(frozen=True, kw_only=True)
class AccountLocked(DomainEvent):
    event_type: ClassVar[str] = "auth.account.locked"
    aggregate_type: ClassVar[str] = AGGREGATE

    email: str
    locked_for_seconds: int
    failed_attempts: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.aggregate_id),
            "email": self.email,
            "locked_for_seconds": self.locked_for_seconds,
            "failed_attempts": self.failed_attempts,
        }


@dataclass(frozen=True, kw_only=True)
class RefreshTokenReuseDetected(DomainEvent):
    """A stolen refresh token was replayed. High-severity security signal.

    Should page someone if the rate rises: a spike means either a leaked token
    store or a bug in the client's rotation handling, and the two need very
    different responses.
    """

    event_type: ClassVar[str] = "auth.token.reuse_detected"
    aggregate_type: ClassVar[str] = AGGREGATE

    family_id: uuid.UUID
    sessions_revoked: int
    ip_hash: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.aggregate_id),
            "family_id": str(self.family_id),
            "sessions_revoked": self.sessions_revoked,
            "ip_hash": self.ip_hash,
        }


@dataclass(frozen=True, kw_only=True)
class UserLoggedOut(DomainEvent):
    event_type: ClassVar[str] = "auth.user.logged_out"
    aggregate_type: ClassVar[str] = AGGREGATE

    session_id: uuid.UUID | None
    all_devices: bool

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.aggregate_id),
            "session_id": str(self.session_id) if self.session_id else None,
            "all_devices": self.all_devices,
        }


@dataclass(frozen=True, kw_only=True)
class OAuthAccountLinked(DomainEvent):
    event_type: ClassVar[str] = "auth.oauth.linked"
    aggregate_type: ClassVar[str] = AGGREGATE

    provider: str
    provider_account_id: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.aggregate_id),
            "provider": self.provider,
            "provider_account_id": self.provider_account_id,
        }


@dataclass(frozen=True, kw_only=True)
class PhoneVerified(DomainEvent):
    event_type: ClassVar[str] = "auth.phone.verified"
    aggregate_type: ClassVar[str] = AGGREGATE

    phone_e164: str

    def to_payload(self) -> dict[str, Any]:
        return {"user_id": str(self.aggregate_id), "phone_e164": self.phone_e164}


@dataclass(frozen=True, kw_only=True)
class RolesChanged(DomainEvent):
    """Privilege change. Always audited, and alerted on for elevated roles.

    ``changed_by`` is what makes the audit trail usable — "who made this person
    an admin?" is the first question asked after an incident.
    """

    event_type: ClassVar[str] = "auth.roles.changed"
    aggregate_type: ClassVar[str] = AGGREGATE

    granted: list[str]
    revoked: list[str]
    changed_by: uuid.UUID | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.aggregate_id),
            "granted": self.granted,
            "revoked": self.revoked,
            "changed_by": str(self.changed_by) if self.changed_by else None,
        }


@dataclass(frozen=True, kw_only=True)
class AccountSuspended(DomainEvent):
    event_type: ClassVar[str] = "auth.account.suspended"
    aggregate_type: ClassVar[str] = AGGREGATE

    reason: str
    suspended_by: uuid.UUID | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_id": str(self.aggregate_id),
            "reason": self.reason,
            "suspended_by": str(self.suspended_by) if self.suspended_by else None,
        }
