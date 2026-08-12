"""HTTP request and response schemas for auth.

These duplicate some validation that the domain also performs, and that is
intentional. The schema rejects obvious nonsense before a use case starts, and
produces field-level errors a form can render. The domain rejects the same
things because a CLI command and a data migration do not pass through here.
The schema is the convenience; the domain is the authority.

Every model carries `json_schema_extra` examples, because these are what
appear in `/docs` and what a mobile developer copies.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.auth.domain.value_objects import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH

# ``EmailStr`` runs email-validator, which is stricter and better-maintained
# than a regex, and normalises the domain part.
Password = Annotated[
    str,
    Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description=f"At least {MIN_PASSWORD_LENGTH} characters. Length matters more than symbols.",
    ),
]


# ══════════════════════════════════════════════════════════════════════════
# Requests
# ══════════════════════════════════════════════════════════════════════════


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    full_name: str | None = Field(default=None, max_length=150)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "priya@example.com",
                "password": "correct-horse-battery",
                "full_name": "Priya Sharma",
            }
        }
    )

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    #: Shown in "where you're signed in". Client-supplied and therefore
    #: untrusted — it is displayed, never acted on.
    device_label: str | None = Field(default=None, max_length=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "priya@example.com", "password": "correct-horse-battery"}
        }
    )


class RefreshRequest(BaseModel):
    """Body is optional: browsers send the refresh token as an HttpOnly cookie
    instead, which JavaScript (and therefore XSS) cannot read."""

    refresh_token: str | None = Field(default=None, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=512)
    all_devices: bool = Field(
        default=False,
        description="Ends every session, including this one. Use after a suspected compromise.",
    )


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=2048)
    new_password: Password


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    new_password: Password


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=2048)


class GoogleLoginRequest(BaseModel):
    """The ID token from Google Sign-In, not an authorization code.

    See ``infrastructure/google_oauth.py`` for why the ID-token flow is used
    for native and SPA clients.
    """

    id_token: str = Field(min_length=20, max_length=4096)
    nonce: str | None = Field(
        default=None,
        max_length=128,
        description="Echo the nonce given to Google. Blocks replay of a captured token.",
    )
    device_label: str | None = Field(default=None, max_length=100)


class RequestOtpRequest(BaseModel):
    phone: str = Field(
        min_length=6,
        max_length=20,
        description="E.164 preferred (+919876543210). A bare 10-digit number is assumed to be +91.",
    )
    purpose: Literal["login", "link_phone"] = "login"

    model_config = ConfigDict(json_schema_extra={"example": {"phone": "+919876543210"}})


class VerifyOtpRequest(BaseModel):
    challenge_id: str = Field(min_length=10, max_length=64)
    code: str = Field(min_length=4, max_length=8, pattern=r"^\d+$")

    model_config = ConfigDict(
        json_schema_extra={"example": {"challenge_id": "s0m3-0paqu3-id", "code": "482913"}}
    )


class ChangeRolesRequest(BaseModel):
    grant: list[str] = Field(default_factory=list, max_length=10)
    revoke: list[str] = Field(default_factory=list, max_length=10)

    model_config = ConfigDict(json_schema_extra={"example": {"grant": ["vendor"], "revoke": []}})


# ══════════════════════════════════════════════════════════════════════════
# Responses
# ══════════════════════════════════════════════════════════════════════════


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"  # noqa: S105 — a scheme name, not a secret
    expires_in: int = Field(description="Access-token lifetime in seconds.")
    refresh_expires_in: int


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    phone: str | None
    avatar_url: str | None
    status: str
    roles: list[str]
    permissions: list[str] = Field(
        description=(
            "Expanded from roles so the UI can hide controls it would be refused for. "
            "A convenience only — the server re-checks every request."
        )
    )
    email_verified: bool
    phone_verified: bool
    has_password: bool
    locale: str
    timezone: str
    vendor_id: uuid.UUID | None
    last_login_at: datetime | None


class AuthResponse(BaseModel):
    tokens: TokenResponse
    user: UserResponse
    is_new_user: bool = Field(
        default=False,
        description="True when this call created the account. Route to onboarding.",
    )


class OtpChallengeResponse(BaseModel):
    challenge_id: str = Field(
        description="Pass this to /auth/otp/verify. The phone number is bound to it server-side."
    )
    expires_in_seconds: int
    resend_after_seconds: int
    phone_masked: str
    debug_code: str | None = Field(
        default=None,
        description="Local and staging only. Never populated in production.",
    )


class SessionResponse(BaseModel):
    id: uuid.UUID
    device_label: str | None
    user_agent: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    is_current: bool


class MessageResponse(BaseModel):
    """For endpoints that deliberately reveal nothing.

    Registration and forgot-password return this whether or not the address is
    registered — see the use-case docstrings for why.
    """

    message: str
    detail: str | None = None
