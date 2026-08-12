"""Password sign-in.

The ordering of the checks in :meth:`LoginUseCase.execute` is the security
design, and it is not the obvious order:

1. Look up the user.
2. **If there is no user, still hash something.** Returning early would make a
   nonexistent account measurably faster than a real one, and that timing
   difference is a user-enumeration oracle that works through any amount of
   generic error messaging.
3. Check lockout **before** verifying the password. Verifying first spends
   64 MiB and ~50 ms of Argon2 on an account that is locked anyway — turning
   our own defence into an amplification vector.
4. Verify.
5. On success, opportunistically upgrade the hash if the cost parameters have
   been raised since it was written.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.clock import Clock
from app.core.logging import get_logger
from app.modules.auth.application.dto import AuthResult, LoginInput
from app.modules.auth.application.ports import PasswordHasherPort, SessionRepository, UserRepository
from app.modules.auth.application.services import TokenIssuer, to_profile
from app.modules.auth.domain import errors
from app.modules.auth.domain.value_objects import Email, InvalidEmailError
from app.shared.application.use_case import Actor

logger = get_logger(__name__)


@dataclass(slots=True)
class LoginUseCase:
    users: UserRepository
    sessions: SessionRepository
    hasher: PasswordHasherPort
    issuer: TokenIssuer
    clock: Clock

    async def execute(self, data: LoginInput, actor: Actor) -> AuthResult:
        now = self.clock.now()

        try:
            email = Email.parse(data.email)
        except InvalidEmailError as exc:
            # Do the dummy hash anyway: a malformed email must not be a faster
            # "no" than a well-formed unknown one.
            self.hasher.verify(data.password, None)
            raise errors.InvalidCredentialsError from exc

        user = await self.users.get_by_email(email)

        if user is None:
            self.hasher.verify(data.password, None)  # constant-ish work
            logger.info("login_failed", reason="unknown_email", email=email.masked)
            raise errors.InvalidCredentialsError

        # Lockout, suspension and deactivation — before any expensive work.
        user.assert_can_attempt_login(now)

        if not self.hasher.verify(data.password, user.password_hash):
            # Also the path for an OAuth-only account, whose hash is None. The
            # caller cannot tell "wrong password" from "this account uses
            # Google", which is the point.
            user.record_failed_login(now, ip_hash=data.context.ip_hash)
            logger.info("login_failed", reason="invalid_password", user_id=str(user.id))
            raise errors.InvalidCredentialsError

        # ── authenticated from here ───────────────────────────────────────

        if user.password_hash and self.hasher.needs_rehash(user.password_hash):
            # The only moment the plaintext is available. Raising the cost
            # parameters is otherwise a change that never reaches existing
            # users.
            user.password_hash = self.hasher.hash(data.password)
            logger.info("password_rehashed", user_id=str(user.id))

        is_new_device = not await self.sessions.has_any_for_device(
            user.id, data.context.ip_hash, data.context.user_agent
        )

        tokens, session = await self.issuer.issue(user, context=data.context, method="password")
        user.record_successful_login(
            now=now,
            method="password",
            session_id=session.id,
            ip_hash=data.context.ip_hash,
            user_agent=data.context.user_agent,
            is_new_device=is_new_device,
        )

        logger.info("login_succeeded", user_id=str(user.id), session_id=str(session.id))
        return AuthResult(tokens=tokens, user=to_profile(user))
