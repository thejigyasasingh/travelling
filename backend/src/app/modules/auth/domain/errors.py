"""Auth domain errors.

Two rules run through this file.

**Authentication failures are deliberately vague.** ``InvalidCredentialsError``
is raised whether the email is unknown, the password is wrong, or the account
is OAuth-only. Distinguishing them hands an attacker a user-enumeration
oracle: "no such account" confirms which of a leaked email list are registered
here, which is exactly the input to a credential-stuffing run.

**Authorisation failures are specific.** Once we know who the caller is,
telling them *what* they lack is helpful and leaks nothing they could not
determine by trying.
"""

from __future__ import annotations

from typing import Any

from app.shared.domain.errors import BusinessRuleViolationError, DomainError


class InvalidCredentialsError(DomainError):
    """Sign-in failed. The message never says why.

    Raised for: unknown email, wrong password, an account that has only ever
    signed in with Google, and a deactivated account.
    """

    #: Authentication failed. 401 is what the whole web
    #: expects, and what every client here already handles.
    status_code = 401

    code = "INVALID_CREDENTIALS"

    def __init__(self) -> None:
        super().__init__("Email or password is incorrect.")


class AccountLockedError(DomainError):
    """Too many failed attempts. Temporary and self-healing.

    Unlike the credential error this *is* specific, because by the time it
    fires the attacker already knows the account exists — and a legitimate
    user who mistyped their password three times needs to be told to wait
    rather than left guessing.
    """

    #: Locked, temporarily. Distinct from 401 so a client can
    #: say "wait" rather than "try a different password".
    status_code = 423

    code = "ACCOUNT_LOCKED"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            "Too many failed sign-in attempts. Please try again later.",
            details={"retry_after_seconds": retry_after_seconds},
        )
        self.retry_after_seconds = retry_after_seconds


class AccountSuspendedError(DomainError):
    """Suspended by an administrator. Requires human intervention, so the user
    is told plainly instead of being left to retry forever."""

    #: Known identity, refused.
    status_code = 403

    code = "ACCOUNT_SUSPENDED"

    def __init__(self, reason: str | None = None) -> None:
        super().__init__(
            "This account has been suspended. Contact support.",
            details={"reason": reason} if reason else {},
        )


class EmailNotVerifiedError(DomainError):
    """Raised by actions that require a verified address, not by sign-in.

    Blocking login until verification is a large drop-off for a marketplace —
    users sign up on mobile, never open the email, and never come back. They
    can browse and manage their profile unverified; booking and payout cannot
    proceed without a reachable address.
    """

    #: Known identity, insufficient standing.
    status_code = 403

    code = "EMAIL_NOT_VERIFIED"

    def __init__(self) -> None:
        super().__init__("Please verify your email address to continue.")


class EmailAlreadyRegisteredError(BusinessRuleViolationError):
    """Only ever surfaced where the caller already proved control of the
    address — never from the public register endpoint, which responds
    identically whether or not the email exists."""

    #: A real conflict with existing state.
    status_code = 409

    code = "EMAIL_ALREADY_REGISTERED"

    def __init__(self) -> None:
        super().__init__("An account already exists for this email address.")


class PhoneAlreadyRegisteredError(BusinessRuleViolationError):
    #: A real conflict with existing state.
    status_code = 409

    code = "PHONE_ALREADY_REGISTERED"

    def __init__(self) -> None:
        super().__init__("This phone number is already linked to another account.")


class InvalidTokenError(DomainError):
    """A verification, reset or refresh token failed validation."""

    #: A bad or forged token is an authentication failure.
    status_code = 401

    code = "INVALID_TOKEN"

    def __init__(self, message: str = "This link is invalid or has expired.") -> None:
        super().__init__(message)


class TokenAlreadyUsedError(InvalidTokenError):
    """Single-use token replayed.

    Password-reset links get forwarded, cached by mail scanners and replayed
    from browser history. Burning the ``jti`` on first use is what makes the
    link genuinely single-use.
    """

    #: A single-use token, spent.
    status_code = 401

    code = "TOKEN_ALREADY_USED"

    def __init__(self) -> None:
        super().__init__("This link has already been used. Request a new one.")


class RefreshTokenReuseError(DomainError):
    """A rotated refresh token was presented again.

    The legitimate client holds the newest token, so a replay of an old one
    means the token was stolen. The entire family is revoked and the user must
    sign in again. Logged as a security event, not a user error.
    """

    #: Token theft was detected and the family revoked. The
    #: client must re-authenticate, which is what 401 tells it to do.
    status_code = 401

    code = "TOKEN_REUSE_DETECTED"

    def __init__(self, family_id: Any = None) -> None:
        super().__init__(
            "Your session has ended for security reasons. Please sign in again.",
            details={"family_id": str(family_id)} if family_id else {},
        )


class SessionExpiredError(DomainError):
    #: **Load-bearing.** Every HTTP client in this project runs a
    #: single-flight refresh on 401. At 409 they do not refresh, and an expired
    #: session surfaces to the user as an error instead of a silent re-auth.
    status_code = 401

    code = "SESSION_EXPIRED"

    def __init__(self) -> None:
        super().__init__("Your session has expired. Please sign in again.")


class PasswordNotSetError(DomainError):
    """The account authenticates through Google only.

    Never raised on the login path — that returns
    :class:`InvalidCredentialsError` so the two are indistinguishable. Raised
    on "change password", where the caller is already authenticated.
    """

    #: Genuinely a conflict: this account has no password to
    #: use. Left at the default, and stated so nobody assumes it was missed.
    status_code = 409

    code = "PASSWORD_NOT_SET"

    def __init__(self) -> None:
        super().__init__(
            "This account signs in with Google. Set a password from your profile first."
        )


class SamePasswordError(BusinessRuleViolationError):
    #: Same reason.
    status_code = 422

    code = "SAME_PASSWORD"

    def __init__(self) -> None:
        super().__init__("The new password must be different from the current one.")


class PasswordPolicyError(BusinessRuleViolationError):
    #: The submitted value is unacceptable — a validation
    #: failure, not a state conflict.
    status_code = 422

    code = "WEAK_PASSWORD"

    def __init__(self, reasons: list[str]) -> None:
        super().__init__(
            "This password does not meet the minimum requirements.",
            details={"reasons": reasons},
        )


# ── OTP ───────────────────────────────────────────────────────────────────


class OtpInvalidError(DomainError):
    """Wrong code, or none outstanding. One error for both, so a probe cannot
    learn whether a code was ever requested for a number."""

    #: A wrong code is a failed authentication attempt.
    status_code = 401

    code = "OTP_INVALID"

    def __init__(self, attempts_remaining: int | None = None) -> None:
        super().__init__(
            "That code is incorrect or has expired.",
            details={"attempts_remaining": attempts_remaining}
            if attempts_remaining is not None
            else {},
        )


class OtpAttemptsExhaustedError(DomainError):
    """The code is destroyed after N wrong guesses.

    Without this a 6-digit code is brute-forceable in a million requests —
    minutes of scripted traffic. Rate limiting alone is not enough, because
    the attacker can spread attempts across many source addresses.
    """

    #: Same reason.
    status_code = 429

    code = "OTP_ATTEMPTS_EXHAUSTED"

    def __init__(self) -> None:
        super().__init__("Too many incorrect attempts. Request a new code.")


class OtpThrottledError(DomainError):
    """Resend requested too soon.

    Every SMS costs money and lands on a real person's phone; an unthrottled
    resend endpoint is both an SMS-pumping fraud vector and a way to harass
    an arbitrary number.
    """

    #: Rate limited. Clients back off on 429; nothing backs off
    #: on 409.
    status_code = 429

    code = "OTP_THROTTLED"

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            "Please wait before requesting another code.",
            details={"retry_after_seconds": retry_after_seconds},
        )


# ── OAuth ─────────────────────────────────────────────────────────────────


class OAuthVerificationError(DomainError):
    #: The provider's assertion did not verify.
    status_code = 401

    code = "OAUTH_VERIFICATION_FAILED"

    def __init__(self, provider: str = "google") -> None:
        super().__init__(
            "We could not verify your identity with the provider.",
            details={"provider": provider},
        )


class OAuthEmailUnverifiedError(DomainError):
    """The provider itself says the address is unverified.

    Trusting it anyway would let anyone who can create an account with an
    unverified address at that provider take over the matching local account.
    """

    #: The provider says the address is unverified.
    status_code = 403

    code = "OAUTH_EMAIL_UNVERIFIED"

    def __init__(self) -> None:
        super().__init__("Your provider account does not have a verified email address.")


class OAuthAccountLinkedElsewhereError(BusinessRuleViolationError):
    #: A real conflict with existing state.
    status_code = 409

    code = "OAUTH_ACCOUNT_ALREADY_LINKED"

    def __init__(self) -> None:
        super().__init__("This provider account is already linked to a different user.")


# ── RBAC ──────────────────────────────────────────────────────────────────


class MissingPermissionError(DomainError):
    """Specific on purpose — see the module docstring."""

    #: Authenticated, and not allowed. 403 is the difference
    #: between "sign in" and "you cannot do this", and a client cannot tell
    #: them apart at 409.
    status_code = 403

    code = "MISSING_PERMISSION"

    def __init__(self, *required: str) -> None:
        super().__init__(
            "You do not have permission to perform this action.",
            details={"required_permissions": sorted(required)},
        )


class RoleNotAssignableError(BusinessRuleViolationError):
    #: A real conflict with existing state.
    status_code = 409

    code = "ROLE_NOT_ASSIGNABLE"

    def __init__(self, role: str) -> None:
        super().__init__(f"The role {role!r} cannot be assigned.", details={"role": role})


class ReauthenticationRequiredError(DomainError):
    """The action is sensitive and the session is too old.

    A 15-minute access token means a stolen one is usable for up to 15
    minutes. That is acceptable for browsing; it is not acceptable for
    changing the password or approving a payout, so those re-prompt.
    """

    #: The session is valid but too old for this action.
    #: 401 with a `WWW-Authenticate` hint is the honest answer.
    status_code = 401

    code = "REAUTHENTICATION_REQUIRED"

    def __init__(self, max_age_seconds: int) -> None:
        super().__init__(
            "Please confirm your password to continue.",
            details={"max_session_age_seconds": max_age_seconds},
        )
