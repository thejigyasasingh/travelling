"""Google sign-in.

We accept a **Google ID token** obtained by the client, verify it server-side
against Google's JWKS, and never see the user's Google password. Two decisions
inside that:

**ID token, not authorization code.** The code flow requires a client secret
and a redirect round-trip, which the mobile apps cannot do safely (a secret
shipped in an APK is not a secret). Google's own recommendation for native and
SPA clients is to send the ID token to the backend. The token is signed by
Google and audience-bound to our client id, so it cannot be replayed at a
different service.

**Account linking happens by verified email, and only by verified email.** If
someone already registered with `priya@gmail.com` and later signs in with
Google using the same address, that is the same person and the accounts link.
But if Google reports the address as *unverified*, linking would let anyone who
can create a Google account claiming an address take over the matching local
account — so it is refused. This is a real, exploited attack pattern, not a
theoretical one.

The linked account keeps its password if it had one; Google becomes an
additional way in, not a replacement.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.clock import Clock
from app.core.logging import get_logger
from app.modules.auth.application.dto import AuthResult, GoogleLoginInput
from app.modules.auth.application.ports import (
    GoogleIdentityProvider,
    SessionRepository,
    UserRepository,
)
from app.modules.auth.application.services import TokenIssuer, to_profile
from app.modules.auth.domain import errors
from app.modules.auth.domain.entities import User
from app.modules.auth.domain.events import OAuthAccountLinked
from app.modules.auth.domain.value_objects import Email
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

PROVIDER = "google"


@dataclass(slots=True)
class GoogleLoginUseCase:
    users: UserRepository
    sessions: SessionRepository
    google: GoogleIdentityProvider
    issuer: TokenIssuer
    clock: Clock

    async def execute(self, data: GoogleLoginInput, actor: Actor) -> AuthResult:
        now = self.clock.now()
        identity = await self.google.verify_id_token(data.id_token, nonce=data.nonce)

        if not identity.email_verified:
            # See the module docstring — this check is what stops account
            # takeover through an unverified provider address.
            logger.warning("google_login_unverified_email", subject=identity.subject)
            raise errors.OAuthEmailUnverifiedError

        email = Email.parse(identity.email)
        is_new_user = False

        # 1. Already linked — the common path after the first sign-in.
        user = await self.users.get_by_oauth(PROVIDER, identity.subject)

        if user is None:
            # 2. An account exists for this verified address: link them.
            user = await self.users.get_by_email(email)

            if user is None:
                # 3. Brand new. Google has verified the address, so the account
                #    starts active rather than pending — sending our own
                #    verification email would be asking the user to prove
                #    something Google already proved.
                user = User.register_via_oauth(
                    email=email,
                    provider_email_verified=True,
                    full_name=identity.full_name,
                    avatar_url=identity.picture,
                    now=now,
                    locale=data.context.locale,
                )
                await self.users.add(user)
                is_new_user = True
            else:
                # Linking to an existing local account also verifies its email
                # if it was still pending: Google has just proved the user
                # controls that inbox.
                if not user.is_email_verified:
                    user.verify_email(now)

            await self.users.link_oauth(
                user_id=user.id,
                provider=PROVIDER,
                provider_account_id=identity.subject,
                email=identity.email,
                raw_profile={
                    "name": identity.full_name,
                    "picture": identity.picture,
                    "hd": identity.hosted_domain,
                },
                now=now,
            )
            user.record(
                OAuthAccountLinked(
                    aggregate_id=user.id,
                    provider=PROVIDER,
                    provider_account_id=identity.subject,
                )
            )

        if not user.is_active:
            # Suspension must not be bypassable by switching sign-in method.
            raise errors.AccountSuspendedError(user.suspension_reason)

        # Fill in details the user never gave us directly. Never overwrite: a
        # name edited in their profile must not be reverted by Google on every
        # sign-in.
        if user.avatar_url is None and identity.picture:
            user.avatar_url = identity.picture
        if user.full_name is None and identity.full_name:
            user.full_name = identity.full_name

        is_new_device = not await self.sessions.has_any_for_device(
            user.id, data.context.ip_hash, data.context.user_agent
        )
        tokens, session = await self.issuer.issue(user, context=data.context, method="google")
        user.record_successful_login(
            now=now,
            method="google",
            session_id=session.id,
            ip_hash=data.context.ip_hash,
            user_agent=data.context.user_agent,
            is_new_device=is_new_device,
        )

        logger.info("google_login_succeeded", user_id=str(user.id), is_new_user=is_new_user)
        return AuthResult(tokens=tokens, user=to_profile(user), is_new_user=is_new_user)
