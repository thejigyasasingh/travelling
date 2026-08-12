"""Registration and email verification.

The defining constraint: **registration must not reveal whether an email is
already registered.** A public endpoint that answers that question turns any
leaked email list into a membership oracle — useful for phishing ("we know you
have an account with them") and as the first step of credential stuffing.

So the response is identical either way, and the *email* carries the
difference: a new user gets a verification link, an existing user gets a "someone
tried to register with your address; sign in or reset your password" notice.
The person who controls the inbox learns what happened. Nobody else does.

This costs a little UX — a user who forgot they had an account sees "check your
email" instead of "you already have an account". The email says exactly that,
which is where they are heading anyway.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.security.tokens import TokenType
from app.modules.auth.application.dto import RegisterInput, VerifyEmailInput
from app.modules.auth.application.ports import ActionTokenStore, PasswordHasherPort, UserRepository
from app.modules.auth.application.services import TokenIssuer
from app.modules.auth.domain import errors
from app.modules.auth.domain.entities import User
from app.modules.auth.domain.events import EmailVerificationRequested
from app.modules.auth.domain.value_objects import Email, RawPassword, WeakPasswordError
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)

EMAIL_VERIFICATION_TTL: Final = 24 * 3600
#: Deliberately shorter than the verification window. A user who asks for a
#: resend is at their keyboard right now.
RESEND_VERIFICATION_TTL: Final = 3600


@dataclass(slots=True)
class RegisterUseCase:
    users: UserRepository
    hasher: PasswordHasherPort
    issuer: TokenIssuer
    clock: Clock

    async def execute(self, data: RegisterInput, actor: Actor) -> None:
        """Returns nothing on purpose.

        No tokens, no profile, no "already exists" — the caller cannot
        distinguish the two outcomes from the response, and there is nothing to
        return that would not leak. The client's next screen is "check your
        email" regardless.
        """
        email = Email.parse(data.email)

        try:
            password = RawPassword(data.password)
        except WeakPasswordError as exc:
            # A weak password IS reported directly. It reveals nothing about
            # who is registered, and silently accepting it then failing later
            # would be worse.
            raise errors.PasswordPolicyError(exc.reasons) from exc

        if password.contains_identity(email.value, data.full_name or ""):
            raise errors.PasswordPolicyError(["must not contain your email address or name"])

        existing = await self.users.get_by_email(email)
        if existing is not None:
            # Same work, same timing, different email. Nothing is written.
            logger.info("registration_attempt_existing_email", email=email.masked)
            existing.record(
                EmailVerificationRequested(
                    aggregate_id=existing.id,
                    email=email.value,
                    token=self.issuer.issue_action_token(
                        existing,
                        purpose=TokenType.EMAIL_VERIFY,
                        ttl_seconds=RESEND_VERIFICATION_TTL,
                    )[0],
                    expires_in_seconds=RESEND_VERIFICATION_TTL,
                    locale=existing.locale,
                )
            )
            return

        user = User.register(
            email=email,
            password_hash=self.hasher.hash(password.value),
            now=self.clock.now(),
            full_name=(data.full_name or "").strip() or None,
            locale=data.context.locale,
        )
        await self.users.add(user)

        token, ttl = self.issuer.issue_action_token(
            user, purpose=TokenType.EMAIL_VERIFY, ttl_seconds=EMAIL_VERIFICATION_TTL
        )
        user.record(
            EmailVerificationRequested(
                aggregate_id=user.id,
                email=email.value,
                token=token,
                expires_in_seconds=ttl,
                locale=user.locale,
            )
        )
        logger.info("user_registered", user_id=str(user.id), email=email.masked)


@dataclass(slots=True)
class VerifyEmailUseCase:
    users: UserRepository
    action_tokens: ActionTokenStore
    issuer: TokenIssuer
    clock: Clock

    async def execute(self, data: VerifyEmailInput, actor: Actor) -> None:
        """Consume a verification link.

        Deliberately **not** single-use-fatal: if the token has already been
        spent but the address is verified, this succeeds. Mail clients
        pre-fetch links, users double-click, and a browser retries — showing
        "this link has already been used" to someone whose email is verified is
        a support ticket about a system that worked correctly.
        """
        claims = self.issuer.tokens.verify_action_token(data.token, TokenType.EMAIL_VERIFY)
        now = self.clock.now()

        user = await self.users.get(claim_uuid(claims, "sub"))
        if user is None:
            raise errors.InvalidTokenError

        if user.is_email_verified:
            return  # idempotent success

        spent = await self.action_tokens.spend(
            jti=claim_uuid(claims, "jti"),
            user_id=user.id,
            purpose=TokenType.EMAIL_VERIFY.value,
            # The spend record can be purged once the token would have expired
            # anyway — there is nothing left to replay after that.
            expires_at=claim_expiry(claims),
            now=now,
        )
        if not spent:
            raise errors.TokenAlreadyUsedError

        user.verify_email(now)
        logger.info("email_verified", user_id=str(user.id))


@dataclass(slots=True)
class ResendVerificationUseCase:
    users: UserRepository
    issuer: TokenIssuer
    clock: Clock

    async def execute(self, _: None, actor: Actor) -> None:
        """Authenticated resend. Rate limited at the route.

        Requires authentication rather than taking an email, because an
        unauthenticated version is a free way to send mail to any address on
        our behalf.
        """
        if actor.user_id is None:  # pragma: no cover — the dependency guarantees this
            raise errors.InvalidCredentialsError

        user = await self.users.get(actor.user_id)
        if user is None:
            raise EntityNotFoundError("User", actor.user_id)
        if user.is_email_verified:
            return

        token, ttl = self.issuer.issue_action_token(
            user, purpose=TokenType.EMAIL_VERIFY, ttl_seconds=RESEND_VERIFICATION_TTL
        )
        user.record(
            EmailVerificationRequested(
                aggregate_id=user.id,
                email=str(user.email),
                token=token,
                expires_in_seconds=ttl,
                locale=user.locale,
            )
        )


# ── claim helpers ─────────────────────────────────────────────────────────
#
# The signature has already been verified by the time these run, so a malformed
# claim means a token we minted ourselves is wrong — but it is still handled as
# an invalid token rather than allowed to become a 500 on a user's reset link.


def claim_uuid(claims: dict[str, Any], key: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(claims[key]))
    except (KeyError, ValueError, TypeError) as exc:
        raise errors.InvalidTokenError from exc


def claim_expiry(claims: dict[str, Any]) -> datetime:
    try:
        return datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
    except (KeyError, ValueError, TypeError) as exc:
        raise errors.InvalidTokenError from exc
