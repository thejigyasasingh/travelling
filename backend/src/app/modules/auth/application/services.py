"""Shared authentication services.

Four use cases end in "the user is now signed in" — password login, Google,
OTP and refresh. Issuing a token pair is identical in all four and is security
critical, so it lives in exactly one place. Four copies would eventually
disagree, and the copy that forgot to bind the session id to the access token
would be the one in production.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.clock import Clock
from app.core.config import SecuritySettings
from app.core.security.tokens import TokenService, TokenType
from app.modules.auth.application.dto import RequestContext, TokenPair, UserProfile
from app.modules.auth.application.ports import SessionRepository
from app.modules.auth.domain.entities import Session, User
from app.modules.auth.domain.rbac import permissions_for


@dataclass(slots=True)
class TokenIssuer:
    """Mints an access/refresh pair and persists the session behind it."""

    tokens: TokenService
    sessions: SessionRepository
    security: SecuritySettings
    clock: Clock

    async def issue(
        self,
        user: User,
        *,
        context: RequestContext,
        method: str,
        family_id: uuid.UUID | None = None,
        parent: Session | None = None,
    ) -> tuple[TokenPair, Session]:
        """Create a session and the tokens that address it.

        ``family_id`` continues an existing chain during rotation; omitted, a
        new chain starts — which is what a fresh sign-in is.

        The access token carries the **session id**, not just the user id. That
        is what lets a single revoked device stop working without invalidating
        the user's other sessions, and what ties an access token to the refresh
        chain it came from.
        """
        now = self.clock.now()

        refresh = self.tokens.issue_refresh_token(now=now, family_id=family_id)

        session = (
            parent.rotate(
                new_token_hash=refresh.token_hash,
                now=now,
                expires_at=refresh.expires_at,
                ip_hash=context.ip_hash,
                user_agent=context.user_agent,
            )
            if parent is not None
            else Session.start(
                user_id=user.id,
                token_hash=refresh.token_hash,
                family_id=refresh.family_id,
                issued_at=now,
                expires_at=refresh.expires_at,
                ip_hash=context.ip_hash,
                user_agent=context.user_agent,
                device_label=context.device_label,
            )
        )
        await self.sessions.add(session)

        access, expires_at = self.tokens.issue_access_token(
            subject=user.id,
            session_id=session.id,
            roles=user.role_names,
            now=now,
            vendor_id=user.vendor_id,
            email_verified=user.is_email_verified,
        )

        pair = TokenPair(
            access_token=access,
            refresh_token=refresh.plaintext,
            expires_in=int((expires_at - now).total_seconds()),
            refresh_expires_in=self.security.refresh_token_ttl_seconds,
        )
        return pair, session

    def issue_action_token(
        self, user: User, *, purpose: TokenType, ttl_seconds: int
    ) -> tuple[str, int]:
        """Email verification and password reset links.

        The token embeds ``pwd_at`` — the moment the password last changed — so
        that changing the password invalidates every outstanding reset link
        without a table scan to find and delete them. A link mailed before the
        change is simply no longer valid against current state.
        """
        extra: dict[str, object] = {}
        if user.password_changed_at is not None:
            extra["pwd_at"] = int(user.password_changed_at.timestamp())

        token = self.tokens.issue_action_token(
            subject=user.id,
            token_type=purpose,
            now=self.clock.now(),
            ttl_seconds=ttl_seconds,
            extra=extra,
        )
        return token, ttl_seconds


def to_profile(user: User, *, created_at: object = None) -> UserProfile:
    """Map the aggregate to the shape clients consume.

    Permissions are expanded from roles here rather than sent as roles alone,
    so a client can hide a button it would be refused for. It is a UI
    convenience only — the server re-checks on every request, because anything
    the client is told it can do is something the client can also lie about.
    """
    return UserProfile(
        id=user.id,
        email=str(user.email),
        full_name=user.full_name,
        phone=str(user.phone) if user.phone else None,
        avatar_url=user.avatar_url,
        status=user.status.value,
        roles=sorted(user.role_names),
        permissions=sorted(p.value for p in permissions_for(user.role_names)),
        email_verified=user.is_email_verified,
        phone_verified=user.is_phone_verified,
        has_password=user.has_password,
        locale=user.locale,
        timezone=user.timezone,
        vendor_id=user.vendor_id,
        created_at=created_at,  # type: ignore[arg-type]
        last_login_at=user.last_login_at,
    )
