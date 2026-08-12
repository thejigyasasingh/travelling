"""Auth module wiring.

Use cases are constructed **per request**, from the request-scoped session and
the process-scoped container. They are plain objects holding four or five
references, so construction is free — and building them here rather than in
``app.container`` keeps the composition root from having to import every
module, which would make the import graph a cycle waiting to happen.

The repositories are also per request, because each holds an identity map tied
to one session. Sharing one across requests would leak aggregates between
users, which is exactly the bug class the identity map exists to avoid inside a
single request.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.container import Container
from app.core.errors import AppError, ErrorCode
from app.infrastructure.database.outbox import persist_events
from app.interface.api.deps import ContainerDep
from app.modules.auth.application.dto import RequestContext
from app.modules.auth.application.services import TokenIssuer
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
from app.modules.auth.domain import errors
from app.modules.auth.infrastructure.google_oauth import GoogleIdentityVerifier
from app.modules.auth.infrastructure.otp_store import RedisOtpService
from app.modules.auth.infrastructure.repositories import (
    SqlActionTokenStore,
    SqlSessionRepository,
    SqlUserRepository,
)


class FeatureDisabledError(AppError):
    """A sign-in method that is switched off for this deployment.

    404, not 403: an endpoint that is not configured should look absent rather
    than forbidden, so a scanner cannot map which providers we support.
    """

    status_code = 404
    code = ErrorCode.NOT_FOUND
    message = "This sign-in method is not available."
    log_level = "info"


class AuthUnitOfWork:
    """Holds the repositories for one request and flushes them together.

    Flushing is what makes "mutate the aggregate and return" sufficient in a
    use case. The domain events the aggregates recorded are drained here and
    appended to the outbox **inside the same transaction** as the state change,
    which is the guarantee the whole outbox design exists for.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = SqlUserRepository(session)
        self.sessions = SqlSessionRepository(session)
        self.action_tokens = SqlActionTokenStore(session)

    async def flush(self) -> None:
        """Write aggregates back and queue their events. Does NOT commit —
        the session scope owns the transaction boundary."""
        await self.users.flush()
        await self.sessions.flush()
        await persist_events(self.session, self.users.pending_events())


#: Domain errors whose *side effects must survive the error*.
#:
#: This is subtle and load-bearing. The natural rule — "roll back on any
#: exception" — is wrong for exactly these cases, because the security state
#: they record is written on the same code path that then raises:
#:
#: * A failed login increments the lockout counter and *then* raises
#:   InvalidCredentialsError. Roll that back and the counter never advances, so
#:   the account never locks and brute-force protection silently does nothing.
#: * Reuse detection revokes the entire token family and *then* raises. Roll
#:   that back and the stolen token keeps working — the detection fires, logs,
#:   alerts, and changes nothing.
#:
#: Both are "the request failed, but we learned something we must not forget".
_PERSIST_ON_FAILURE: tuple[type[BaseException], ...] = (
    errors.InvalidCredentialsError,
    errors.AccountLockedError,
    errors.RefreshTokenReuseError,
    errors.OtpInvalidError,
    errors.OtpAttemptsExhaustedError,
)


async def get_auth_uow(container: ContainerDep) -> AsyncIterator[AuthUnitOfWork]:
    """Transaction scope for an auth command.

    Commits on success. Rolls back on an unexpected failure — but commits
    first for the errors in ``_PERSIST_ON_FAILURE``; see the note there for
    why that exception to the rule is required rather than convenient.
    """
    async with container.database.write_session() as session:
        uow = AuthUnitOfWork(session)
        try:
            yield uow
        except _PERSIST_ON_FAILURE:
            await uow.flush()
            await session.commit()
            raise
        await uow.flush()


AuthUow = Annotated[AuthUnitOfWork, Depends(get_auth_uow)]


def _issuer(container: Container, uow: AuthUnitOfWork) -> TokenIssuer:
    return TokenIssuer(
        tokens=container.tokens,
        sessions=uow.sessions,
        security=container.settings.security,
        clock=container.clock,
    )


def _otp(container: Container) -> RedisOtpService:
    if not container.settings.auth.otp_enabled:
        raise FeatureDisabledError
    return RedisOtpService(
        container.redis.cache,
        expose_debug_code=container.settings.auth.otp_expose_debug_code,
    )


def _google(container: Container) -> GoogleIdentityVerifier:
    cfg = container.settings.auth
    if not cfg.google_enabled:
        raise FeatureDisabledError
    return GoogleIdentityVerifier(client_ids=cfg.google_client_ids)


# ══════════════════════════════════════════════════════════════════════════
# Use-case providers
# ══════════════════════════════════════════════════════════════════════════


def register_uc(container: ContainerDep, uow: AuthUow) -> RegisterUseCase:
    return RegisterUseCase(
        users=uow.users,
        hasher=container.password_hasher,
        issuer=_issuer(container, uow),
        clock=container.clock,
    )


def login_uc(container: ContainerDep, uow: AuthUow) -> LoginUseCase:
    return LoginUseCase(
        users=uow.users,
        sessions=uow.sessions,
        hasher=container.password_hasher,
        issuer=_issuer(container, uow),
        clock=container.clock,
    )


def refresh_uc(container: ContainerDep, uow: AuthUow) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(
        users=uow.users,
        sessions=uow.sessions,
        tokens=container.tokens,
        issuer=_issuer(container, uow),
        security=container.settings.security,
        clock=container.clock,
    )


def logout_uc(container: ContainerDep, uow: AuthUow) -> LogoutUseCase:
    return LogoutUseCase(sessions=uow.sessions, users=uow.users, clock=container.clock)


def forgot_password_uc(container: ContainerDep, uow: AuthUow) -> ForgotPasswordUseCase:
    return ForgotPasswordUseCase(
        users=uow.users, issuer=_issuer(container, uow), clock=container.clock
    )


def reset_password_uc(container: ContainerDep, uow: AuthUow) -> ResetPasswordUseCase:
    return ResetPasswordUseCase(
        users=uow.users,
        sessions=uow.sessions,
        action_tokens=uow.action_tokens,
        hasher=container.password_hasher,
        issuer=_issuer(container, uow),
        clock=container.clock,
    )


def change_password_uc(container: ContainerDep, uow: AuthUow) -> ChangePasswordUseCase:
    return ChangePasswordUseCase(
        users=uow.users,
        sessions=uow.sessions,
        hasher=container.password_hasher,
        clock=container.clock,
    )


def verify_email_uc(container: ContainerDep, uow: AuthUow) -> VerifyEmailUseCase:
    return VerifyEmailUseCase(
        users=uow.users,
        action_tokens=uow.action_tokens,
        issuer=_issuer(container, uow),
        clock=container.clock,
    )


def resend_verification_uc(container: ContainerDep, uow: AuthUow) -> ResendVerificationUseCase:
    return ResendVerificationUseCase(
        users=uow.users, issuer=_issuer(container, uow), clock=container.clock
    )


def google_login_uc(container: ContainerDep, uow: AuthUow) -> GoogleLoginUseCase:
    return GoogleLoginUseCase(
        users=uow.users,
        sessions=uow.sessions,
        google=_google(container),
        issuer=_issuer(container, uow),
        clock=container.clock,
    )


def request_otp_uc(container: ContainerDep) -> RequestOtpUseCase:
    return RequestOtpUseCase(otp=_otp(container), clock=container.clock)


def verify_otp_uc(container: ContainerDep, uow: AuthUow) -> VerifyOtpUseCase:
    return VerifyOtpUseCase(
        users=uow.users,
        sessions=uow.sessions,
        otp=_otp(container),
        issuer=_issuer(container, uow),
        clock=container.clock,
    )


def link_phone_uc(container: ContainerDep, uow: AuthUow) -> LinkPhoneUseCase:
    return LinkPhoneUseCase(users=uow.users, otp=_otp(container), clock=container.clock)


def list_sessions_uc(container: ContainerDep, uow: AuthUow) -> ListSessionsUseCase:
    return ListSessionsUseCase(sessions=uow.sessions, clock=container.clock)


def revoke_session_uc(container: ContainerDep, uow: AuthUow) -> RevokeSessionUseCase:
    return RevokeSessionUseCase(sessions=uow.sessions, clock=container.clock)


def profile_uc(uow: AuthUow) -> GetProfileUseCase:
    return GetProfileUseCase(users=uow.users)


def change_roles_uc(container: ContainerDep, uow: AuthUow) -> ChangeRolesUseCase:
    return ChangeRolesUseCase(users=uow.users, sessions=uow.sessions, clock=container.clock)


# ── request context ───────────────────────────────────────────────────────


def request_context(request: Request) -> RequestContext:
    """Ambient caller facts, with the IP already hashed.

    Hashed here — at the boundary — rather than deeper in, so that no layer
    below ever holds a raw address. The salt is the JWT key id, which is stable
    within a deployment and rotates with the keys, so hashes are comparable for
    device recognition but not correlatable across deployments.
    """
    settings = request.app.state.settings
    forwarded = request.headers.get("x-forwarded-for")
    raw_ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else None)
    )
    ip_hash = (
        hashlib.sha256(f"{settings.security.jwt_key_id}:{raw_ip}".encode()).hexdigest()[:32]
        if raw_ip
        else None
    )

    return RequestContext(
        ip_hash=ip_hash,
        user_agent=(request.headers.get("user-agent") or "")[:400] or None,
        locale=(request.headers.get("accept-language") or "en-IN").split(",")[0][:10],
    )


ContextDep = Annotated[RequestContext, Depends(request_context)]
