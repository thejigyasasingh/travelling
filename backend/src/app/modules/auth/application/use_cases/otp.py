"""Phone/OTP sign-in.

The dominant sign-in method in the Indian market, and the one with the most
ways to get it wrong. The controls that matter:

**The challenge id, not the phone number, is what gets verified.** ``/verify``
takes an opaque challenge id and a code; it never takes a phone number. If it
took both, an attacker could request a code to *their own* phone and then
submit it against *someone else's* number — the code would be valid and the
number would be attacker-chosen. Binding the number to the challenge server-side
makes that impossible to express.

**Codes die after a few wrong guesses.** Six digits is a million possibilities,
which is minutes of scripted traffic. Rate limiting alone does not close it —
an attacker spreads attempts across addresses — so the challenge itself is
destroyed after three failures.

**Resend is throttled server-side.** Every SMS costs real money and lands on a
real person's phone. An unthrottled resend is both an SMS-pumping fraud vector
(attacker earns a share of the carrier fee) and a way to harass any number.

**Codes are stored hashed.** A Redis dump, or an operator running ``GET``,
should not yield a working credential for a session in flight.

An OTP-registered user gets a placeholder email so that a single identity
column stays non-null and unique. They are prompted for a real address before
booking, where a reachable email becomes genuinely necessary (confirmations,
invoices, cancellation notices).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.clock import Clock
from app.core.logging import get_logger
from app.modules.auth.application.dto import (
    AuthResult,
    OtpChallengeResult,
    RequestOtpInput,
    VerifyOtpInput,
)
from app.modules.auth.application.ports import OtpService, SessionRepository, UserRepository
from app.modules.auth.application.services import TokenIssuer, to_profile
from app.modules.auth.domain import errors
from app.modules.auth.domain.entities import User
from app.modules.auth.domain.value_objects import (
    Email,
    InvalidPhoneNumberError,
    PhoneNumber,
)
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

#: Domain for placeholder addresses. Non-routable by design — a typo'd real
#: domain would send account mail to a stranger.
OTP_PLACEHOLDER_DOMAIN = "phone.roamingwandering.invalid"


def placeholder_email(phone: PhoneNumber) -> Email:
    return Email.parse(f"{phone.value.lstrip('+')}@{OTP_PLACEHOLDER_DOMAIN}")


@dataclass(slots=True)
class RequestOtpUseCase:
    otp: OtpService
    clock: Clock

    async def execute(self, data: RequestOtpInput, actor: Actor) -> OtpChallengeResult:
        """Send a code. Says nothing about whether the number is registered.

        A response that differed for known and unknown numbers would let anyone
        test a phone list against our user base — and phone numbers are far
        easier to enumerate than emails.
        """
        try:
            phone = PhoneNumber.parse(data.phone)
        except InvalidPhoneNumberError as exc:
            # The one case that IS reported: the input is unusable, and staying
            # silent would leave the user staring at a screen waiting for an
            # SMS that was never addressable.
            raise errors.OtpInvalidError from exc

        challenge = await self.otp.issue(phone, purpose=data.purpose)
        logger.info("otp_issued", phone=phone.masked, purpose=data.purpose)

        return OtpChallengeResult(
            challenge_id=challenge.challenge_id,
            expires_in_seconds=challenge.expires_in_seconds,
            resend_after_seconds=challenge.resend_after_seconds,
            phone_masked=phone.masked,
            debug_code=challenge.debug_code,
        )


@dataclass(slots=True)
class VerifyOtpUseCase:
    users: UserRepository
    sessions: SessionRepository
    otp: OtpService
    issuer: TokenIssuer
    clock: Clock

    async def execute(self, data: VerifyOtpInput, actor: Actor) -> AuthResult:
        """Verify the code and sign in, registering the user if new.

        Registration-on-verify is deliberate: a separate "now create your
        account" step after proving phone ownership adds a form for no security
        gain, and it is where most of the drop-off in this flow happens.
        """
        now = self.clock.now()

        # The phone comes back from the challenge — the caller never supplies
        # it. See the module docstring.
        phone = await self.otp.verify(data.challenge_id, data.code)

        user = await self.users.get_by_phone(phone)
        is_new_user = False

        if user is None:
            user = User.register_via_phone(
                phone=phone,
                email=placeholder_email(phone),
                now=now,
                locale=data.context.locale,
            )
            await self.users.add(user)
            is_new_user = True
            logger.info("user_registered_via_otp", user_id=str(user.id), phone=phone.masked)
        else:
            if not user.is_active:
                raise errors.AccountSuspendedError(user.suspension_reason)
            # Possessing the number is proof of control, even if an earlier
            # signup left it unverified.
            if not user.is_phone_verified:
                user.verify_phone(phone, now)

        is_new_device = not await self.sessions.has_any_for_device(
            user.id, data.context.ip_hash, data.context.user_agent
        )
        tokens, session = await self.issuer.issue(user, context=data.context, method="otp")
        user.record_successful_login(
            now=now,
            method="otp",
            session_id=session.id,
            ip_hash=data.context.ip_hash,
            user_agent=data.context.user_agent,
            is_new_device=is_new_device,
        )

        logger.info("otp_login_succeeded", user_id=str(user.id), is_new_user=is_new_user)
        return AuthResult(tokens=tokens, user=to_profile(user), is_new_user=is_new_user)


@dataclass(slots=True)
class LinkPhoneUseCase:
    """Attach a verified phone to an already-authenticated account.

    Separate from sign-in because the security question is different: here we
    know who the caller is and are proving they control a *number*, so the
    number must not already belong to someone else.
    """

    users: UserRepository
    otp: OtpService
    clock: Clock

    async def execute(self, data: VerifyOtpInput, actor: Actor) -> None:
        if actor.user_id is None:  # pragma: no cover — route requires auth
            raise errors.InvalidCredentialsError

        phone = await self.otp.verify(data.challenge_id, data.code)

        owner = await self.users.get_by_phone(phone)
        if owner is not None and owner.id != actor.user_id:
            raise errors.PhoneAlreadyRegisteredError

        user = await self.users.get(actor.user_id)
        if user is None:  # pragma: no cover
            raise errors.InvalidCredentialsError

        user.verify_phone(phone, self.clock.now())
        logger.info("phone_linked", user_id=str(user.id), phone=phone.masked)
