"""Forgot password, reset password, change password.

Password reset is the most attacked flow in any application, because it is by
definition a way to take over an account without knowing the password. Four
properties hold it together:

**The response never reveals whether the email is registered.** Always 202,
always the same latency. Otherwise the endpoint is a free membership oracle.

**The link is single-use.** The ``jti`` is burned atomically on first use.
Reset links get forwarded, cached by corporate mail scanners, and replayed
from browser history; without burning, all of those work.

**The link dies when the password changes.** The token embeds ``pwd_at``. If
the password has changed since the token was minted — because the user reset
twice, or because the real owner beat the attacker to it — the older link is
already dead, with no table scan needed to find it.

**A successful reset revokes every session.** If the account was compromised,
the attacker's refresh tokens must stop working; leaving them alive makes the
reset cosmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.security.tokens import TokenType
from app.modules.auth.application.dto import (
    ChangePasswordInput,
    ForgotPasswordInput,
    ResetPasswordInput,
)
from app.modules.auth.application.ports import (
    ActionTokenStore,
    PasswordHasherPort,
    SessionRepository,
    UserRepository,
)
from app.modules.auth.application.services import TokenIssuer
from app.modules.auth.application.use_cases.registration import claim_expiry, claim_uuid
from app.modules.auth.domain import errors
from app.modules.auth.domain.events import PasswordResetRequested
from app.modules.auth.domain.value_objects import (
    Email,
    InvalidEmailError,
    RawPassword,
    WeakPasswordError,
)
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)

#: One hour. Long enough to walk to a computer, short enough that a link
#: sitting in a shared inbox is not a standing takeover.
RESET_TOKEN_TTL: Final = 3600


@dataclass(slots=True)
class ForgotPasswordUseCase:
    users: UserRepository
    issuer: TokenIssuer
    clock: Clock

    async def execute(self, data: ForgotPasswordInput, actor: Actor) -> None:
        """Always returns ``None``, always looks the same from outside."""
        try:
            email = Email.parse(data.email)
        except InvalidEmailError:
            logger.info("password_reset_malformed_email")
            return  # still a silent success

        user = await self.users.get_by_email(email)
        if user is None:
            logger.info("password_reset_unknown_email", email=email.masked)
            return

        if not user.has_password:
            # OAuth-only account. Sending a reset link would set a password on
            # an account whose owner never chose one — a takeover path if the
            # mailbox is compromised but the Google account is not. The
            # notification consumer sends "you sign in with Google" instead.
            logger.info("password_reset_oauth_only", user_id=str(user.id))
            return

        if not user.is_active:
            logger.info("password_reset_inactive_account", user_id=str(user.id))
            return

        token, ttl = self.issuer.issue_action_token(
            user, purpose=TokenType.PASSWORD_RESET, ttl_seconds=RESET_TOKEN_TTL
        )
        user.record(
            PasswordResetRequested(
                aggregate_id=user.id,
                email=str(user.email),
                token=token,
                expires_in_seconds=ttl,
                requested_ip_hash=data.context.ip_hash,
                locale=user.locale,
            )
        )
        logger.info("password_reset_requested", user_id=str(user.id))


@dataclass(slots=True)
class ResetPasswordUseCase:
    users: UserRepository
    sessions: SessionRepository
    action_tokens: ActionTokenStore
    hasher: PasswordHasherPort
    issuer: TokenIssuer
    clock: Clock

    async def execute(self, data: ResetPasswordInput, actor: Actor) -> None:
        claims = self.issuer.tokens.verify_action_token(data.token, TokenType.PASSWORD_RESET)
        now = self.clock.now()

        user = await self.users.get(claim_uuid(claims, "sub"))
        if user is None or not user.has_password:
            raise errors.InvalidTokenError

        # The password has moved on since this link was minted, so the link is
        # already dead — no table scan needed to find and delete it.
        #
        # Both sides are truncated to whole seconds. `pwd_at` is stored as an
        # integer JWT claim, while `password_changed_at` keeps microsecond
        # precision; comparing them directly makes a freshly minted token look
        # older than the change it was minted from, and *every* reset fails.
        minted_for = claims.get("pwd_at")
        if (
            minted_for is not None
            and user.password_changed_at is not None
            and int(minted_for) < int(user.password_changed_at.timestamp())
        ):
            logger.info("password_reset_stale_token", user_id=str(user.id))
            raise errors.InvalidTokenError

        try:
            new_password = RawPassword(data.new_password)
        except WeakPasswordError as exc:
            raise errors.PasswordPolicyError(exc.reasons) from exc

        if new_password.contains_identity(str(user.email), user.full_name or ""):
            raise errors.PasswordPolicyError(["must not contain your email address or name"])

        if self.hasher.verify(new_password.value, user.password_hash):
            # Reusing the current password after a suspected compromise defeats
            # the purpose of resetting.
            raise errors.SamePasswordError

        # Burn the token *before* applying the change. If the write fails the
        # user requests a new link; if we burned it after, two concurrent
        # clicks could both pass the check and race on the password.
        spent = await self.action_tokens.spend(
            jti=claim_uuid(claims, "jti"),
            user_id=user.id,
            purpose=TokenType.PASSWORD_RESET.value,
            expires_at=claim_expiry(claims),
            now=now,
        )
        if not spent:
            raise errors.TokenAlreadyUsedError

        revoked = await self.sessions.revoke_all_for_user(user.id, now=now, reason="password_reset")
        user.set_password(
            self.hasher.hash(new_password.value),
            now=now,
            via_reset=True,
            sessions_revoked=revoked,
        )
        logger.info("password_reset_completed", user_id=str(user.id), sessions_revoked=revoked)


@dataclass(slots=True)
class ChangePasswordUseCase:
    users: UserRepository
    sessions: SessionRepository
    hasher: PasswordHasherPort
    clock: Clock

    async def execute(self, data: ChangePasswordInput, actor: Actor) -> int:
        """Authenticated change. Requires the current password.

        A valid access token is *not* sufficient on its own: the token may have
        been stolen, and letting a stolen token change the password converts a
        15-minute window into permanent ownership of the account. Knowing the
        current password is what proves the caller is the owner.

        Every *other* session is revoked; the caller's own survives, because
        signing someone out of the device they are actively using in response
        to a routine security action trains them not to do it.
        """
        if actor.user_id is None:  # pragma: no cover — route requires auth
            raise errors.InvalidCredentialsError

        now = self.clock.now()
        user = await self.users.get(actor.user_id)
        if user is None:
            raise EntityNotFoundError("User", actor.user_id)

        user.assert_can_change_password()

        if not self.hasher.verify(data.current_password, user.password_hash):
            user.record_failed_login(now)
            raise errors.InvalidCredentialsError

        try:
            new_password = RawPassword(data.new_password)
        except WeakPasswordError as exc:
            raise errors.PasswordPolicyError(exc.reasons) from exc

        if self.hasher.verify(new_password.value, user.password_hash):
            raise errors.SamePasswordError
        if new_password.contains_identity(str(user.email), user.full_name or ""):
            raise errors.PasswordPolicyError(["must not contain your email address or name"])

        revoked = await self.sessions.revoke_all_for_user(
            user.id, now=now, reason="password_changed", except_session=actor.session_id
        )
        user.set_password(
            self.hasher.hash(new_password.value),
            now=now,
            via_reset=False,
            sessions_revoked=revoked,
        )
        logger.info("password_changed", user_id=str(user.id), sessions_revoked=revoked)
        return revoked
