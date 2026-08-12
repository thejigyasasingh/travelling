"""Auth HTTP endpoints.

Handlers are thin on purpose: parse, call one use case, map the result. Every
decision worth arguing about lives in the domain or the use case, where it is
testable without HTTP.

**Refresh tokens are returned in the body *and* as an HttpOnly cookie.** The
two audiences have opposite needs:

* A browser should never let JavaScript touch a 30-day credential — one XSS and
  the attacker has a month of access. An HttpOnly cookie is unreadable by
  script, so the token survives an XSS that steals everything else.
* A mobile app has no cookie jar worth relying on and stores the token in the
  platform keychain, which is the right place for it.

Sending both lets each client use the one that suits it and ignore the other.
The cookie is `SameSite=Lax` and scoped to the refresh path, so a cross-site
form post cannot trigger a silent refresh.

Status codes carry meaning: **202** where we accepted the request but are
deliberately not saying what happened (register, forgot-password), **204** where
there is genuinely nothing to return.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status

from app.core.config import Settings
from app.core.errors import UnauthenticatedError
from app.core.serialization import dto_dict
from app.interface.api.deps import ActorDep, SettingsDep
from app.modules.auth.application import dto
from app.modules.auth.application.use_cases.google import GoogleLoginUseCase
from app.modules.auth.application.use_cases.login import LoginUseCase
from app.modules.auth.application.use_cases.otp import (
    LinkPhoneUseCase,
    RequestOtpUseCase,
    VerifyOtpUseCase,
)
from app.modules.auth.application.use_cases.password import (
    ChangePasswordUseCase,
    ForgotPasswordUseCase,
    ResetPasswordUseCase,
)
from app.modules.auth.application.use_cases.registration import (
    RegisterUseCase,
    ResendVerificationUseCase,
    VerifyEmailUseCase,
)
from app.modules.auth.application.use_cases.roles import ChangeRolesUseCase, GetProfileUseCase
from app.modules.auth.application.use_cases.sessions import (
    ListSessionsUseCase,
    RevokeSessionUseCase,
)
from app.modules.auth.application.use_cases.tokens import LogoutUseCase, RefreshTokenUseCase
from app.modules.auth.interface import deps
from app.modules.auth.interface.permissions import CanGrantRolesDep
from app.modules.auth.interface.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    ChangeRolesRequest,
    ForgotPasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    OtpChallengeResponse,
    RefreshRequest,
    RegisterRequest,
    RequestOtpRequest,
    ResetPasswordRequest,
    SessionResponse,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
    VerifyOtpRequest,
)
from app.shared.application.use_case import Actor

router = APIRouter(prefix="/auth", tags=["auth"])

ANONYMOUS = Actor(user_id=None)

# Documented on every endpoint that can produce them, so a client developer
# reading /docs sees the failure modes without reading our source.
_AUTH_RESPONSES: dict[int | str, dict[str, str]] = {
    401: {"description": "Invalid or missing credentials"},
    423: {"description": "Account temporarily locked after repeated failures"},
    429: {"description": "Rate limited"},
}


# ══════════════════════════════════════════════════════════════════════════
# Cookie handling
# ══════════════════════════════════════════════════════════════════════════


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    cfg = settings.auth
    if not cfg.refresh_cookie_enabled:
        return
    response.set_cookie(
        key=cfg.refresh_cookie_name,
        value=token,
        max_age=settings.security.refresh_token_ttl_seconds,
        # HttpOnly is the entire point: script cannot read it, so an XSS
        # cannot exfiltrate a 30-day credential.
        httponly=True,
        secure=cfg.refresh_cookie_secure,
        samesite=cfg.refresh_cookie_samesite,
        domain=cfg.refresh_cookie_domain,
        # Scoped to the endpoints that need it, so it is not attached to every
        # API request and cannot leak through an unrelated handler.
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    cfg = settings.auth
    if cfg.refresh_cookie_enabled:
        response.delete_cookie(
            key=cfg.refresh_cookie_name, path="/api/v1/auth", domain=cfg.refresh_cookie_domain
        )


def _auth_response(result: dto.AuthResult, response: Response, settings: Settings) -> AuthResponse:
    _set_refresh_cookie(response, result.tokens.refresh_token, settings)
    return AuthResponse(
        tokens=TokenResponse(**dto_dict(result.tokens)),
        user=UserResponse(**dto_dict(result.user, exclude=frozenset({"created_at"}))),
        is_new_user=result.is_new_user,
    )


# ══════════════════════════════════════════════════════════════════════════
# Registration and verification
# ══════════════════════════════════════════════════════════════════════════


@router.post(
    "/register",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageResponse,
    summary="Create an account",
    responses={422: {"description": "Weak password or malformed email"}},
)
async def register(
    body: RegisterRequest,
    context: deps.ContextDep,
    use_case: Annotated[RegisterUseCase, Depends(deps.register_uc)],
) -> MessageResponse:
    """Always responds the same way, registered or not.

    The response deliberately carries **no tokens and no indication of whether
    the address was already in use** — that would make this endpoint a
    membership oracle for any leaked email list. The difference goes to the
    inbox: a new user receives a verification link, an existing one receives a
    "someone tried to register with your address" notice.

    A weak password *is* reported, because it reveals nothing about who is
    registered.
    """
    await use_case.execute(
        dto.RegisterInput(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            context=context,
        ),
        ANONYMOUS,
    )
    return MessageResponse(
        message="Check your email to continue.",
        detail="If that address can receive mail, we have sent it a link.",
    )


@router.post(
    "/email/verify",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Verify an email address",
    responses={400: {"description": "Link is invalid, expired or already used"}},
)
async def verify_email(
    body: VerifyEmailRequest,
    use_case: Annotated[VerifyEmailUseCase, Depends(deps.verify_email_uc)],
) -> None:
    """Idempotent: clicking twice succeeds. Mail clients pre-fetch links and
    users double-click, and "already used" on an address that *is* verified is
    a support ticket about correct behaviour."""
    await use_case.execute(dto.VerifyEmailInput(token=body.token), ANONYMOUS)


@router.post(
    "/email/resend",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageResponse,
    summary="Resend the verification email",
)
async def resend_verification(
    actor: ActorDep,
    use_case: Annotated[ResendVerificationUseCase, Depends(deps.resend_verification_uc)],
) -> MessageResponse:
    """Authenticated. An unauthenticated version would be a way to send mail to
    any address on our behalf."""
    await use_case.execute(None, actor)
    return MessageResponse(message="Verification email sent.")


# ══════════════════════════════════════════════════════════════════════════
# Sign-in
# ══════════════════════════════════════════════════════════════════════════


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Sign in with email and password",
    responses=_AUTH_RESPONSES,
)
async def login(
    body: LoginRequest,
    response: Response,
    settings: SettingsDep,
    context: deps.ContextDep,
    use_case: Annotated[LoginUseCase, Depends(deps.login_uc)],
) -> AuthResponse:
    """Wrong password and unknown account are indistinguishable — same error,
    same status, same approximate timing. Rate limited to 5 attempts per 15
    minutes per IP, and the account itself locks progressively."""
    ctx = dto.RequestContext(
        ip_hash=context.ip_hash,
        user_agent=context.user_agent,
        device_label=body.device_label,
        locale=context.locale,
    )
    result = await use_case.execute(
        dto.LoginInput(email=body.email, password=body.password, context=ctx), ANONYMOUS
    )
    return _auth_response(result, response, settings)


@router.post(
    "/google",
    response_model=AuthResponse,
    summary="Sign in with Google",
    responses={
        401: {"description": "The ID token could not be verified"},
        404: {"description": "Google sign-in is not enabled for this deployment"},
    },
)
async def google_login(
    body: GoogleLoginRequest,
    response: Response,
    settings: SettingsDep,
    context: deps.ContextDep,
    use_case: Annotated[GoogleLoginUseCase, Depends(deps.google_login_uc)],
) -> AuthResponse:
    """Send the **ID token** from Google Sign-In, not an authorization code.

    Links to an existing account when the verified email matches. An account
    Google reports as *unverified* is refused — otherwise anyone able to create
    a Google account claiming an address could take over the matching local
    account.
    """
    ctx = dto.RequestContext(
        ip_hash=context.ip_hash,
        user_agent=context.user_agent,
        device_label=body.device_label,
        locale=context.locale,
    )
    result = await use_case.execute(
        dto.GoogleLoginInput(id_token=body.id_token, nonce=body.nonce, context=ctx), ANONYMOUS
    )
    return _auth_response(result, response, settings)


@router.post(
    "/otp/request",
    response_model=OtpChallengeResponse,
    summary="Send a one-time code by SMS",
    responses={429: {"description": "Resend cooldown or hourly quota"}},
)
async def request_otp(
    body: RequestOtpRequest,
    context: deps.ContextDep,
    use_case: Annotated[RequestOtpUseCase, Depends(deps.request_otp_uc)],
) -> OtpChallengeResponse:
    """Says nothing about whether the number is registered.

    Returns an opaque `challenge_id`; the phone number is bound to it
    server-side and cannot be changed by the client at verify time.
    """
    result = await use_case.execute(
        dto.RequestOtpInput(phone=body.phone, purpose=body.purpose, context=context), ANONYMOUS
    )
    return OtpChallengeResponse(**dto_dict(result))


@router.post(
    "/otp/verify",
    response_model=AuthResponse,
    summary="Sign in with a one-time code",
    responses={401: {"description": "Wrong or expired code"}},
)
async def verify_otp(
    body: VerifyOtpRequest,
    response: Response,
    settings: SettingsDep,
    context: deps.ContextDep,
    use_case: Annotated[VerifyOtpUseCase, Depends(deps.verify_otp_uc)],
) -> AuthResponse:
    """Creates the account if the number is new — proving control of the phone
    is the whole signup. Three wrong guesses destroy the challenge."""
    result = await use_case.execute(
        dto.VerifyOtpInput(challenge_id=body.challenge_id, code=body.code, context=context),
        ANONYMOUS,
    )
    return _auth_response(result, response, settings)


@router.post(
    "/phone/link",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Attach a verified phone number to your account",
)
async def link_phone(
    body: VerifyOtpRequest,
    actor: ActorDep,
    context: deps.ContextDep,
    use_case: Annotated[LinkPhoneUseCase, Depends(deps.link_phone_uc)],
) -> None:
    await use_case.execute(
        dto.VerifyOtpInput(challenge_id=body.challenge_id, code=body.code, context=context), actor
    )


# ══════════════════════════════════════════════════════════════════════════
# Token lifecycle
# ══════════════════════════════════════════════════════════════════════════


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Exchange a refresh token for a new pair",
    responses={
        401: {
            "description": (
                "Token is unknown, expired, revoked, or was already used — "
                "the last of which revokes every session in the family."
            )
        }
    },
)
async def refresh(
    body: RefreshRequest,
    response: Response,
    settings: SettingsDep,
    context: deps.ContextDep,
    use_case: Annotated[RefreshTokenUseCase, Depends(deps.refresh_uc)],
    rw_refresh: Annotated[str | None, Cookie()] = None,
) -> AuthResponse:
    """Rotating: the old token stops working the moment this succeeds.

    Presenting an already-rotated token is treated as theft — the whole token
    family is revoked and the user must sign in again — *except* within a few
    seconds of rotation, which is assumed to be a client that lost the
    response on a flaky connection.

    The token may come from the body (mobile) or the HttpOnly cookie
    (browsers); the body wins if both are present.
    """
    token = body.refresh_token or rw_refresh
    if not token:
        raise UnauthenticatedError("A refresh token is required.")

    result = await use_case.execute(
        dto.RefreshInput(refresh_token=token, context=context), ANONYMOUS
    )
    return _auth_response(result, response, settings)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="End this session, or all of them",
)
async def logout(
    body: LogoutRequest,
    response: Response,
    actor: ActorDep,
    settings: SettingsDep,
    use_case: Annotated[LogoutUseCase, Depends(deps.logout_uc)],
    rw_refresh: Annotated[str | None, Cookie()] = None,
) -> None:
    """Always succeeds, even for an unknown token — the caller's intent is
    "end my session", and that state is already true.

    Note that outstanding **access** tokens remain valid until they expire
    (≤15 minutes). That is the documented cost of stateless access tokens and
    the reason their lifetime is short.
    """
    await use_case.execute(
        dto.LogoutInput(
            refresh_token=body.refresh_token or rw_refresh, all_devices=body.all_devices
        ),
        actor,
    )
    _clear_refresh_cookie(response, settings)


# ══════════════════════════════════════════════════════════════════════════
# Password
# ══════════════════════════════════════════════════════════════════════════


@router.post(
    "/password/forgot",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageResponse,
    summary="Request a password-reset link",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    context: deps.ContextDep,
    use_case: Annotated[ForgotPasswordUseCase, Depends(deps.forgot_password_uc)],
) -> MessageResponse:
    """Always 202, whether or not the address is registered.

    Rate limited to 3 per hour per IP. Accounts that sign in only with Google
    receive a "you use Google" email rather than a reset link — setting a
    password on an account whose owner never chose one would be a takeover path.
    """
    await use_case.execute(dto.ForgotPasswordInput(email=body.email, context=context), ANONYMOUS)
    return MessageResponse(message="If that address has an account, a reset link is on its way.")


@router.post(
    "/password/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Set a new password using a reset link",
    responses={400: {"description": "Link invalid, expired or already used"}},
)
async def reset_password(
    body: ResetPasswordRequest,
    response: Response,
    settings: SettingsDep,
    use_case: Annotated[ResetPasswordUseCase, Depends(deps.reset_password_uc)],
) -> None:
    """Single-use, and **revokes every session** on success — if the account
    was compromised, the attacker's refresh tokens must stop working, or the
    reset is cosmetic."""
    await use_case.execute(
        dto.ResetPasswordInput(token=body.token, new_password=body.new_password), ANONYMOUS
    )
    _clear_refresh_cookie(response, settings)


@router.post(
    "/password/change",
    response_model=MessageResponse,
    summary="Change your password",
    responses={401: {"description": "Current password is wrong"}},
)
async def change_password(
    body: ChangePasswordRequest,
    actor: ActorDep,
    use_case: Annotated[ChangePasswordUseCase, Depends(deps.change_password_uc)],
) -> MessageResponse:
    """Requires the **current** password, not just a valid access token.

    A stolen access token must not be enough to take permanent ownership of an
    account; knowing the current password is what proves the caller is the
    owner. Every other session is ended; this one survives.
    """
    revoked = await use_case.execute(
        dto.ChangePasswordInput(
            current_password=body.current_password, new_password=body.new_password
        ),
        actor,
    )
    return MessageResponse(
        message="Password updated.",
        detail=f"{revoked} other session(s) were signed out." if revoked else None,
    )


# ══════════════════════════════════════════════════════════════════════════
# Profile and sessions
# ══════════════════════════════════════════════════════════════════════════


@router.get("/me", response_model=UserResponse, summary="Your profile, roles and permissions")
async def me(
    actor: ActorDep,
    use_case: Annotated[GetProfileUseCase, Depends(deps.profile_uc)],
) -> UserResponse:
    """Read from the database, not decoded from the token.

    The token is a snapshot up to 15 minutes old: a role granted or an email
    verified since it was issued would not appear in it.
    """
    profile = await use_case.execute(None, actor)
    return UserResponse(**dto_dict(profile, exclude=frozenset({"created_at"})))


@router.get(
    "/sessions",
    response_model=list[SessionResponse],
    summary="Devices where you are signed in",
)
async def list_sessions(
    actor: ActorDep,
    use_case: Annotated[ListSessionsUseCase, Depends(deps.list_sessions_uc)],
) -> list[SessionResponse]:
    """One entry per device — rotated ancestors are collapsed, or a single
    phone would appear dozens of times."""
    rows = await use_case.execute(None, actor)
    return [SessionResponse(**dto_dict(row)) for row in rows]


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Sign out a specific device",
    responses={404: {"description": "No such session belonging to you"}},
)
async def revoke_session(
    session_id: uuid.UUID,
    actor: ActorDep,
    use_case: Annotated[RevokeSessionUseCase, Depends(deps.revoke_session_uc)],
) -> None:
    """Scoped to your own sessions: another user's id resolves to 404 rather
    than revoking their session."""
    await use_case.execute(session_id, actor)


# ══════════════════════════════════════════════════════════════════════════
# Administration
# ══════════════════════════════════════════════════════════════════════════


@router.patch(
    "/users/{user_id}/roles",
    response_model=UserResponse,
    summary="Grant or revoke roles",
    responses={403: {"description": "Requires role:grant:any"}},
)
async def change_roles(
    user_id: uuid.UUID,
    body: ChangeRolesRequest,
    actor: CanGrantRolesDep,
    use_case: Annotated[ChangeRolesUseCase, Depends(deps.change_roles_uc)],
) -> UserResponse:
    """Superadmin only, and never on yourself — self-grant is the classic
    escalation path.

    Revocations end the user's sessions immediately, because a revoked role
    would otherwise linger in their access token for up to 15 minutes.
    """
    profile = await use_case.execute(
        dto.ChangeRolesInput(user_id=user_id, grant=body.grant, revoke=body.revoke), actor
    )
    return UserResponse(**dto_dict(profile, exclude=frozenset({"created_at"})))
