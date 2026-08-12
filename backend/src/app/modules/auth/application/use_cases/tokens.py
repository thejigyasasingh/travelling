"""Refresh rotation and logout.

Refresh rotation with reuse detection is the single most important mechanism in
this module, so it is worth stating the threat plainly.

A refresh token lives for 30 days on a device we do not control. If it leaks —
a stolen phone, a malicious app reading shared storage, an XSS in a webview —
the attacker can mint access tokens for a month, and nothing about their
requests looks unusual. Signature checks cannot help: the token *is* valid.

**Rotation** means each refresh returns a new token and spends the old one. The
legitimate client always holds the newest one. So if a *spent* token is ever
presented again, two parties hold tokens from the same chain — a theft — and
the correct response is to revoke the whole family and force a real sign-in.
That converts a silent month-long compromise into a single failed request plus
a security event.

The complication is that a lost response looks exactly like a replay. A phone
on a flaky connection rotates, the response never arrives, and it retries with
the token it still has. Treating that as theft logs out honest users constantly
and buries the real signal in false positives. Hence the **grace window**: a
token rotated within the last few seconds returns the same successor instead of
burning the family.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.clock import Clock
from app.core.config import SecuritySettings
from app.core.logging import get_logger
from app.core.security.tokens import TokenService
from app.modules.auth.application.dto import AuthResult, LogoutInput, RefreshInput
from app.modules.auth.application.ports import SessionRepository, UserRepository
from app.modules.auth.application.services import TokenIssuer, to_profile
from app.modules.auth.domain import errors
from app.modules.auth.domain.entities import Session, _WithinRotationGrace
from app.modules.auth.domain.events import RefreshTokenReuseDetected, UserLoggedOut
from app.shared.application.use_case import Actor

logger = get_logger(__name__)


@dataclass(slots=True)
class RefreshTokenUseCase:
    users: UserRepository
    sessions: SessionRepository
    tokens: TokenService
    issuer: TokenIssuer
    security: SecuritySettings
    clock: Clock

    async def execute(self, data: RefreshInput, actor: Actor) -> AuthResult:
        now = self.clock.now()
        token_hash = TokenService.hash_refresh_token(data.refresh_token)

        session = await self.sessions.get_by_token_hash(token_hash)
        if session is None:
            # Unknown token. Could be forged, could be from a family already
            # burned by an earlier reuse. Either way there is nothing to revoke
            # and nothing useful to say.
            logger.info("refresh_failed", reason="unknown_token")
            raise errors.SessionExpiredError

        try:
            session.assert_usable(now, grace_seconds=self.security.refresh_rotation_grace_seconds)
        except _WithinRotationGrace:
            # A lost response, not an attack. The client is holding a token we
            # already rotated moments ago; re-issuing from its successor keeps
            # them signed in without minting a second live chain.
            logger.info("refresh_within_grace", session_id=str(session.id))
            return await self._reissue_from_grace(session, data, now)
        except errors.RefreshTokenReuseError:
            await self._handle_reuse(session, data, now)
            raise

        user = await self.users.get(session.user_id)
        if user is None or not user.is_active:
            await self.sessions.revoke_family(session.family_id, now=now, reason="user_inactive")
            raise errors.SessionExpiredError

        # A password change invalidates every session issued before it, without
        # having to find and delete those rows at change time.
        if user.credentials_issued_before(session.issued_at):
            await self.sessions.revoke_family(session.family_id, now=now, reason="password_changed")
            logger.info("refresh_rejected_stale_credentials", user_id=str(user.id))
            raise errors.SessionExpiredError

        pair, new_session = await self.issuer.issue(
            user,
            context=data.context,
            method="refresh",
            family_id=session.family_id,
            parent=session,
        )
        logger.info(
            "refresh_rotated",
            user_id=str(user.id),
            family_id=str(session.family_id),
            session_id=str(new_session.id),
        )
        return AuthResult(tokens=pair, user=to_profile(user))

    async def _handle_reuse(self, session: Session, data: RefreshInput, now: datetime) -> None:
        """Burn the family and shout about it.

        Revoking only the replayed token would leave the attacker's newer one
        working. The whole chain goes, because we cannot tell which party is
        the legitimate one — and forcing both to sign in again is a minor
        inconvenience for the real user versus an ongoing compromise.
        """
        revoked = await self.sessions.revoke_family(
            session.family_id, now=now, reason="token_reuse_detected"
        )
        user = await self.users.get(session.user_id)
        if user is not None:
            user.record(
                RefreshTokenReuseDetected(
                    aggregate_id=user.id,
                    family_id=session.family_id,
                    sessions_revoked=revoked,
                    ip_hash=data.context.ip_hash,
                )
            )
        logger.warning(
            "refresh_token_reuse_detected",
            user_id=str(session.user_id),
            family_id=str(session.family_id),
            sessions_revoked=revoked,
        )

    async def _reissue_from_grace(
        self, session: Session, data: RefreshInput, now: datetime
    ) -> AuthResult:
        """Mint a fresh pair on the same family for a client that lost its
        response. Does not re-mark the parent, so the grace window does not
        slide forward indefinitely under a retry loop."""
        user = await self.users.get(session.user_id)
        if user is None or not user.is_active:
            raise errors.SessionExpiredError

        pair, _ = await self.issuer.issue(
            user, context=data.context, method="refresh", family_id=session.family_id
        )
        return AuthResult(tokens=pair, user=to_profile(user))


@dataclass(slots=True)
class LogoutUseCase:
    sessions: SessionRepository
    users: UserRepository
    clock: Clock

    async def execute(self, data: LogoutInput, actor: Actor) -> int:
        """Revoke this device, or every device. Returns how many sessions ended.

        **Always succeeds.** An unknown or already-expired token still returns
        success: the caller's intent is "end my session", and that state is
        already true. Returning an error would leave clients unsure whether to
        clear their local tokens — and the safe thing for them to do is clear
        them regardless.

        Revoking the refresh token does not kill outstanding *access* tokens;
        those remain valid until they expire (≤15 min). That is the documented
        trade of stateless access tokens, and the reason their TTL is short.
        """
        now = self.clock.now()

        if data.all_devices:
            if actor.user_id is None:  # pragma: no cover — route requires auth
                return 0
            count = await self.sessions.revoke_all_for_user(
                actor.user_id, now=now, reason="user_logout_all"
            )
            user = await self.users.get(actor.user_id)
            if user is not None:
                user.record(UserLoggedOut(aggregate_id=user.id, session_id=None, all_devices=True))
            logger.info("logout_all_devices", user_id=str(actor.user_id), sessions=count)
            return count

        if not data.refresh_token:
            return 0

        token_hash = TokenService.hash_refresh_token(data.refresh_token)
        session = await self.sessions.get_by_token_hash(token_hash)
        if session is None:
            return 0

        # Revoke the family, not the single row: the point of logout is that
        # this device stops working, and the device may already have rotated.
        count = await self.sessions.revoke_family(session.family_id, now=now, reason="user_logout")
        user = await self.users.get(session.user_id)
        if user is not None:
            user.record(
                UserLoggedOut(aggregate_id=user.id, session_id=session.id, all_devices=False)
            )
        logger.info("logout", user_id=str(session.user_id), session_id=str(session.id))
        return count
