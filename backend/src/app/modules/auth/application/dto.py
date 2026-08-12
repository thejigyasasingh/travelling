"""Application-layer DTOs.

Plain dataclasses, not pydantic models. These cross the boundary between a use
case and *whatever* is calling it — HTTP today, a CLI command and a Celery task
alongside it. Returning a pydantic model would make the application layer
depend on the web framework's serialisation library, and would push HTTP-shaped
concerns (field aliases, JSON schema) into code that has no business knowing
about them.

The interface layer maps these to its own response schemas.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Ambient facts about the caller that the domain needs for security
    decisions but that are not part of the business request.

    The IP arrives already hashed. The raw address is personal data under GDPR
    and the DPDP Act, and nothing downstream needs it — "is this the same
    client as last time?" is what device recognition actually asks, and a
    stable hash answers it.
    """

    ip_hash: str | None = None
    user_agent: str | None = None
    device_label: str | None = None
    locale: str = "en-IN"


@dataclass(frozen=True, slots=True)
class TokenPair:
    """What a successful authentication produces.

    ``refresh_token`` is returned to the caller exactly once and is never
    persisted in this form — only its SHA-256 hash reaches the database.
    """

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"  # noqa: S105 — a scheme name, not a secret
    expires_in: int = 900
    refresh_expires_in: int = 2_592_000


@dataclass(frozen=True, slots=True)
class UserProfile:
    id: uuid.UUID
    email: str
    full_name: str | None
    phone: str | None
    avatar_url: str | None
    status: str
    roles: list[str]
    permissions: list[str]
    email_verified: bool
    phone_verified: bool
    has_password: bool
    locale: str
    timezone: str
    vendor_id: uuid.UUID | None
    created_at: datetime | None = None
    last_login_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AuthResult:
    tokens: TokenPair
    user: UserProfile
    #: True when this call created the account. Lets a client route a
    #: first-time Google user into onboarding instead of the home screen.
    is_new_user: bool = False


@dataclass(frozen=True, slots=True)
class OtpChallengeResult:
    """Returned by "send me a code".

    Carries the *masked* phone so the UI can render "we sent a code to
    ***3210" without the client having to keep the number it typed — and
    without the API echoing a full number back, which would make the endpoint a
    number-formatting oracle.
    """

    challenge_id: str
    expires_in_seconds: int
    resend_after_seconds: int
    phone_masked: str
    #: Populated only outside production, so local and staging can complete the
    #: flow without an SMS gateway. Gated in the OTP service, not here.
    debug_code: str | None = None


@dataclass(frozen=True, slots=True)
class SessionInfo:
    """One row in "where you're signed in"."""

    id: uuid.UUID
    device_label: str | None
    user_agent: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    is_current: bool


# ── inputs ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RegisterInput:
    email: str
    password: str
    full_name: str | None = None
    context: RequestContext = field(default_factory=RequestContext)


@dataclass(frozen=True, slots=True)
class LoginInput:
    email: str
    password: str
    context: RequestContext = field(default_factory=RequestContext)


@dataclass(frozen=True, slots=True)
class RefreshInput:
    refresh_token: str
    context: RequestContext = field(default_factory=RequestContext)


@dataclass(frozen=True, slots=True)
class LogoutInput:
    refresh_token: str | None = None
    all_devices: bool = False


@dataclass(frozen=True, slots=True)
class ForgotPasswordInput:
    email: str
    context: RequestContext = field(default_factory=RequestContext)


@dataclass(frozen=True, slots=True)
class ResetPasswordInput:
    token: str
    new_password: str


@dataclass(frozen=True, slots=True)
class ChangePasswordInput:
    current_password: str
    new_password: str


@dataclass(frozen=True, slots=True)
class VerifyEmailInput:
    token: str


@dataclass(frozen=True, slots=True)
class GoogleLoginInput:
    id_token: str
    nonce: str | None = None
    context: RequestContext = field(default_factory=RequestContext)


@dataclass(frozen=True, slots=True)
class RequestOtpInput:
    phone: str
    purpose: str = "login"
    context: RequestContext = field(default_factory=RequestContext)


@dataclass(frozen=True, slots=True)
class VerifyOtpInput:
    challenge_id: str
    code: str
    context: RequestContext = field(default_factory=RequestContext)


@dataclass(frozen=True, slots=True)
class ChangeRolesInput:
    user_id: uuid.UUID
    grant: list[str] = field(default_factory=list)
    revoke: list[str] = field(default_factory=list)
