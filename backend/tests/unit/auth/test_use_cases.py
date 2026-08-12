"""Use-case behaviour, driven entirely by in-memory fakes.

These prove the properties that a route test cannot reach cheaply: that
registration is silent about existing accounts, that a login failure still
records the attempt, that reuse detection burns the family, and that a reset
kills every session.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.security.tokens import TokenService
from app.modules.auth.application import dto
from app.modules.auth.application.services import TokenIssuer
from app.modules.auth.application.use_cases.google import GoogleLoginUseCase
from app.modules.auth.application.use_cases.login import LoginUseCase
from app.modules.auth.application.use_cases.otp import VerifyOtpUseCase
from app.modules.auth.application.use_cases.password import (
    ChangePasswordUseCase,
    ForgotPasswordUseCase,
    ResetPasswordUseCase,
)
from app.modules.auth.application.use_cases.registration import RegisterUseCase
from app.modules.auth.application.use_cases.tokens import LogoutUseCase, RefreshTokenUseCase
from app.modules.auth.domain import errors
from app.modules.auth.domain.entities import LOCKOUT_THRESHOLD, User
from app.modules.auth.domain.value_objects import Email
from app.shared.application.use_case import Actor
from tests.unit.auth.fakes import (
    FakeActionTokenStore,
    FakeClock,
    FakeGoogleProvider,
    FakeOtpService,
    FakePasswordHasher,
    FakeSessionRepository,
    FakeUserRepository,
)

pytestmark = pytest.mark.unit

# Anchored to real time, not a fixed date: these use cases mint genuine RS256
# tokens and PyJWT checks `exp` against the system clock, so a clock parked in
# the past would issue tokens it then rejects as expired. Determinism still
# comes from FakeClock — every assertion here is about *elapsed* time, which
# the test advances explicitly.
NOW = datetime.now(UTC).replace(microsecond=0)
ANON = Actor(user_id=None)
CTX = dto.RequestContext(ip_hash="iphash", user_agent="RW-iOS/2.1")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


@pytest.fixture
def hasher() -> FakePasswordHasher:
    return FakePasswordHasher()


@pytest.fixture
def users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def sessions() -> FakeSessionRepository:
    return FakeSessionRepository()


@pytest.fixture
def issuer(
    token_service: TokenService, sessions: FakeSessionRepository, clock: FakeClock, settings
):
    return TokenIssuer(
        tokens=token_service, sessions=sessions, security=settings.security, clock=clock
    )


def existing_user(
    hasher: FakePasswordHasher,
    password: str = "correct horse battery",  # noqa: S107 — a fixture passphrase
) -> User:
    user = User.register(
        email=Email.parse("priya@example.com"),
        password_hash=hasher.hash(password),
        now=NOW,
        full_name="Priya Sharma",
    )
    user.verify_email(NOW)
    user.pull_events()
    return user


# ══════════════════════════════════════════════════════════════════════════
# Registration
# ══════════════════════════════════════════════════════════════════════════


class TestRegister:
    async def test_creates_a_user_and_requests_verification(
        self, users, hasher, issuer, clock
    ) -> None:
        uc = RegisterUseCase(users=users, hasher=hasher, issuer=issuer, clock=clock)
        await uc.execute(
            dto.RegisterInput(
                email="Priya@Example.com", password="correct horse battery", context=CTX
            ),
            ANON,
        )
        assert len(users.added) == 1
        assert str(users.added[0].email) == "priya@example.com"  # normalised
        types = [e.event_type for e in users.events()]
        assert "auth.user.registered" in types
        assert "auth.email.verification_requested" in types

    async def test_existing_email_writes_nothing_and_looks_identical(
        self, users, hasher, issuer, clock
    ) -> None:
        """The user-enumeration defence.

        No exception, no tokens, no new row — the caller cannot tell this apart
        from a successful registration. The difference goes to the inbox.
        """
        await users.add(existing_user(hasher))
        users.added.clear()  # ignore the seeded row; we care about the delta
        uc = RegisterUseCase(users=users, hasher=hasher, issuer=issuer, clock=clock)

        result = await uc.execute(
            dto.RegisterInput(email="priya@example.com", password="a different one", context=CTX),
            ANON,
        )

        assert result is None
        assert users.added == []
        # The *existing* account is told someone tried.
        assert "auth.email.verification_requested" in [e.event_type for e in users.events()]

    async def test_weak_password_is_reported_directly(self, users, hasher, issuer, clock) -> None:
        # Reveals nothing about who is registered, so there is no reason to
        # hide it — and hiding it would leave the user unable to proceed.
        uc = RegisterUseCase(users=users, hasher=hasher, issuer=issuer, clock=clock)
        with pytest.raises(errors.PasswordPolicyError):
            await uc.execute(
                dto.RegisterInput(email="new@example.com", password="short", context=CTX), ANON
            )

    async def test_password_containing_the_email_is_rejected(
        self, users, hasher, issuer, clock
    ) -> None:
        uc = RegisterUseCase(users=users, hasher=hasher, issuer=issuer, clock=clock)
        with pytest.raises(errors.PasswordPolicyError):
            await uc.execute(
                dto.RegisterInput(
                    email="priyasharma@example.com", password="priyasharma-2026", context=CTX
                ),
                ANON,
            )


# ══════════════════════════════════════════════════════════════════════════
# Login
# ══════════════════════════════════════════════════════════════════════════


class TestLogin:
    @pytest.fixture
    def use_case(self, users, sessions, hasher, issuer, clock):
        return LoginUseCase(
            users=users, sessions=sessions, hasher=hasher, issuer=issuer, clock=clock
        )

    async def test_successful_login_issues_a_pair_and_a_session(
        self, use_case, users, sessions, hasher
    ) -> None:
        await users.add(existing_user(hasher))
        result = await use_case.execute(
            dto.LoginInput(
                email="priya@example.com", password="correct horse battery", context=CTX
            ),
            ANON,
        )
        assert result.tokens.access_token
        assert result.tokens.refresh_token
        assert len(sessions.sessions) == 1
        assert "auth.user.logged_in" in [e.event_type for e in users.events()]

    async def test_unknown_email_still_burns_a_hash(self, use_case, hasher) -> None:
        """The timing-equalisation path.

        Returning early on an unknown account makes it measurably faster than a
        real one, which is a user-enumeration oracle no amount of generic error
        messaging can close.
        """
        with pytest.raises(errors.InvalidCredentialsError):
            await use_case.execute(
                dto.LoginInput(email="nobody@example.com", password="whatever", context=CTX), ANON
            )
        assert hasher.dummy_verifications == 1

    async def test_malformed_email_also_burns_a_hash(self, use_case, hasher) -> None:
        with pytest.raises(errors.InvalidCredentialsError):
            await use_case.execute(
                dto.LoginInput(email="not-an-email", password="whatever", context=CTX), ANON
            )
        assert hasher.dummy_verifications == 1

    async def test_wrong_password_records_the_attempt(self, use_case, users, hasher) -> None:
        user = existing_user(hasher)
        await users.add(user)
        with pytest.raises(errors.InvalidCredentialsError):
            await use_case.execute(
                dto.LoginInput(email="priya@example.com", password="wrong", context=CTX), ANON
            )
        assert user.failed_login_attempts == 1

    async def test_repeated_failures_lock_the_account(self, use_case, users, hasher) -> None:
        user = existing_user(hasher)
        await users.add(user)
        for _ in range(LOCKOUT_THRESHOLD):
            with pytest.raises(errors.InvalidCredentialsError):
                await use_case.execute(
                    dto.LoginInput(email="priya@example.com", password="wrong", context=CTX), ANON
                )
        # The next attempt is refused before the password is even checked.
        with pytest.raises(errors.AccountLockedError):
            await use_case.execute(
                dto.LoginInput(
                    email="priya@example.com", password="correct horse battery", context=CTX
                ),
                ANON,
            )

    async def test_oauth_only_account_is_indistinguishable_from_a_wrong_password(
        self, use_case, users
    ) -> None:
        user = User.register_via_oauth(
            email=Email.parse("priya@example.com"),
            provider_email_verified=True,
            full_name=None,
            avatar_url=None,
            now=NOW,
        )
        await users.add(user)
        with pytest.raises(errors.InvalidCredentialsError):
            await use_case.execute(
                dto.LoginInput(email="priya@example.com", password="anything", context=CTX), ANON
            )

    async def test_suspended_account_gets_the_generic_error(self, use_case, users, hasher) -> None:
        user = existing_user(hasher)
        user.suspend(reason="fraud", by=None, now=NOW)
        await users.add(user)
        with pytest.raises(errors.InvalidCredentialsError):
            await use_case.execute(
                dto.LoginInput(
                    email="priya@example.com", password="correct horse battery", context=CTX
                ),
                ANON,
            )


# ══════════════════════════════════════════════════════════════════════════
# Refresh
# ══════════════════════════════════════════════════════════════════════════


class TestRefresh:
    @pytest.fixture
    def use_case(self, users, sessions, token_service, issuer, clock, settings):
        return RefreshTokenUseCase(
            users=users,
            sessions=sessions,
            tokens=token_service,
            issuer=issuer,
            security=settings.security,
            clock=clock,
        )

    async def _sign_in(self, users, sessions, hasher, issuer, clock) -> tuple[User, str]:
        user = existing_user(hasher)
        await users.add(user)
        login = LoginUseCase(
            users=users, sessions=sessions, hasher=hasher, issuer=issuer, clock=clock
        )
        result = await login.execute(
            dto.LoginInput(
                email="priya@example.com", password="correct horse battery", context=CTX
            ),
            ANON,
        )
        return user, result.tokens.refresh_token

    async def test_rotation_returns_a_new_pair(
        self, use_case, users, sessions, hasher, issuer, clock
    ) -> None:
        _, refresh_token = await self._sign_in(users, sessions, hasher, issuer, clock)
        result = await use_case.execute(
            dto.RefreshInput(refresh_token=refresh_token, context=CTX), ANON
        )
        assert result.tokens.refresh_token != refresh_token

    async def test_the_old_token_stops_working(
        self, use_case, users, sessions, hasher, issuer, clock
    ) -> None:
        _, refresh_token = await self._sign_in(users, sessions, hasher, issuer, clock)
        await use_case.execute(dto.RefreshInput(refresh_token=refresh_token, context=CTX), ANON)

        clock.advance(timedelta(seconds=60))  # well past the grace window
        with pytest.raises(errors.RefreshTokenReuseError):
            await use_case.execute(dto.RefreshInput(refresh_token=refresh_token, context=CTX), ANON)

    async def test_reuse_burns_the_entire_family(
        self, use_case, users, sessions, hasher, issuer, clock
    ) -> None:
        """Revoking only the replayed token would leave the attacker's newer
        one working — the detection would fire and change nothing."""
        _, first = await self._sign_in(users, sessions, hasher, issuer, clock)
        second = (
            await use_case.execute(dto.RefreshInput(refresh_token=first, context=CTX), ANON)
        ).tokens.refresh_token

        clock.advance(timedelta(seconds=60))
        with pytest.raises(errors.RefreshTokenReuseError):
            await use_case.execute(dto.RefreshInput(refresh_token=first, context=CTX), ANON)

        # The successor the attacker (or the user) holds is dead too.
        with pytest.raises(errors.SessionExpiredError):
            await use_case.execute(dto.RefreshInput(refresh_token=second, context=CTX), ANON)

        assert all(s.is_revoked for s in sessions.sessions.values())
        assert "auth.token.reuse_detected" in [e.event_type for e in users.events()]

    async def test_replay_within_the_grace_window_is_forgiven(
        self, use_case, users, sessions, hasher, issuer, clock
    ) -> None:
        # A mobile client that lost the response, not an attacker.
        _, first = await self._sign_in(users, sessions, hasher, issuer, clock)
        await use_case.execute(dto.RefreshInput(refresh_token=first, context=CTX), ANON)

        clock.advance(timedelta(seconds=2))
        result = await use_case.execute(dto.RefreshInput(refresh_token=first, context=CTX), ANON)
        assert result.tokens.access_token
        assert not any(s.is_revoked for s in sessions.sessions.values())

    async def test_unknown_token_is_rejected_without_a_stack_trace(self, use_case) -> None:
        with pytest.raises(errors.SessionExpiredError):
            await use_case.execute(dto.RefreshInput(refresh_token="nonsense", context=CTX), ANON)

    async def test_a_password_change_invalidates_live_sessions(
        self, use_case, users, sessions, hasher, issuer, clock
    ) -> None:
        user, refresh_token = await self._sign_in(users, sessions, hasher, issuer, clock)
        clock.advance(timedelta(minutes=5))
        user.set_password(hasher.hash("brand new passphrase"), now=clock.now(), via_reset=False)

        with pytest.raises(errors.SessionExpiredError):
            await use_case.execute(dto.RefreshInput(refresh_token=refresh_token, context=CTX), ANON)


# ══════════════════════════════════════════════════════════════════════════
# Password recovery
# ══════════════════════════════════════════════════════════════════════════


class TestPasswordRecovery:
    async def test_forgot_password_is_silent_for_unknown_addresses(
        self, users, issuer, clock
    ) -> None:
        uc = ForgotPasswordUseCase(users=users, issuer=issuer, clock=clock)
        assert await uc.execute(dto.ForgotPasswordInput(email="nobody@example.com"), ANON) is None
        assert users.events() == []

    async def test_forgot_password_is_silent_for_oauth_only_accounts(
        self, users, issuer, clock
    ) -> None:
        # Setting a password on an account whose owner never chose one is a
        # takeover path if the mailbox is compromised but Google is not.
        user = User.register_via_oauth(
            email=Email.parse("priya@example.com"),
            provider_email_verified=True,
            full_name=None,
            avatar_url=None,
            now=NOW,
        )
        user.pull_events()
        await users.add(user)

        uc = ForgotPasswordUseCase(users=users, issuer=issuer, clock=clock)
        await uc.execute(dto.ForgotPasswordInput(email="priya@example.com"), ANON)
        assert "auth.password.reset_requested" not in [e.event_type for e in users.events()]

    async def test_reset_revokes_every_session(
        self, users, sessions, hasher, issuer, clock, token_service
    ) -> None:
        """If the account was compromised, the attacker's refresh tokens must
        stop working — otherwise the reset is cosmetic."""
        user = existing_user(hasher)
        await users.add(user)
        login = LoginUseCase(
            users=users, sessions=sessions, hasher=hasher, issuer=issuer, clock=clock
        )
        await login.execute(
            dto.LoginInput(
                email="priya@example.com", password="correct horse battery", context=CTX
            ),
            ANON,
        )
        user.pull_events()

        forgot = ForgotPasswordUseCase(users=users, issuer=issuer, clock=clock)
        await forgot.execute(dto.ForgotPasswordInput(email="priya@example.com"), ANON)
        token = next(
            e.token for e in user.pull_events() if e.event_type == "auth.password.reset_requested"
        )

        store = FakeActionTokenStore()
        reset = ResetPasswordUseCase(
            users=users,
            sessions=sessions,
            action_tokens=store,
            hasher=hasher,
            issuer=issuer,
            clock=clock,
        )
        await reset.execute(
            dto.ResetPasswordInput(token=token, new_password="a whole new passphrase"), ANON
        )

        assert all(s.is_revoked for s in sessions.sessions.values())
        assert hasher.verify("a whole new passphrase", user.password_hash)

    async def test_reset_works_when_the_clock_has_sub_second_precision(
        self, users, sessions, hasher, issuer, clock
    ) -> None:
        """Regression: `pwd_at` is an integer JWT claim, but
        `password_changed_at` keeps microseconds.

        Comparing them directly made a freshly minted token look older than the
        change it came from, so every reset failed with "invalid link". The
        unit suite missed it because its clock was anchored on a whole second;
        a real SystemClock is not.
        """
        clock._now = clock._now.replace(microsecond=123_456)
        user = existing_user(hasher)
        user.set_password(hasher.hash("correct horse battery"), now=clock.now(), via_reset=False)
        user.pull_events()
        await users.add(user)

        forgot = ForgotPasswordUseCase(users=users, issuer=issuer, clock=clock)
        await forgot.execute(dto.ForgotPasswordInput(email="priya@example.com"), ANON)
        token = next(
            e.token for e in user.pull_events() if e.event_type == "auth.password.reset_requested"
        )

        reset = ResetPasswordUseCase(
            users=users,
            sessions=sessions,
            action_tokens=FakeActionTokenStore(),
            hasher=hasher,
            issuer=issuer,
            clock=clock,
        )
        await reset.execute(
            dto.ResetPasswordInput(token=token, new_password="a whole new passphrase"), ANON
        )
        assert hasher.verify("a whole new passphrase", user.password_hash)

    async def test_a_reset_link_works_exactly_once(
        self, users, sessions, hasher, issuer, clock
    ) -> None:
        # Reset links get forwarded, cached by mail scanners and replayed from
        # browser history.
        user = existing_user(hasher)
        await users.add(user)
        forgot = ForgotPasswordUseCase(users=users, issuer=issuer, clock=clock)
        await forgot.execute(dto.ForgotPasswordInput(email="priya@example.com"), ANON)
        token = next(
            e.token for e in user.pull_events() if e.event_type == "auth.password.reset_requested"
        )

        store = FakeActionTokenStore()
        reset = ResetPasswordUseCase(
            users=users,
            sessions=sessions,
            action_tokens=store,
            hasher=hasher,
            issuer=issuer,
            clock=clock,
        )
        await reset.execute(
            dto.ResetPasswordInput(token=token, new_password="a whole new passphrase"), ANON
        )
        with pytest.raises(errors.InvalidTokenError):
            await reset.execute(
                dto.ResetPasswordInput(token=token, new_password="yet another passphrase"), ANON
            )

    async def test_change_password_requires_the_current_one(
        self, users, sessions, hasher, clock
    ) -> None:
        # A stolen access token must not be enough to take permanent ownership.
        user = existing_user(hasher)
        await users.add(user)
        uc = ChangePasswordUseCase(users=users, sessions=sessions, hasher=hasher, clock=clock)
        with pytest.raises(errors.InvalidCredentialsError):
            await uc.execute(
                dto.ChangePasswordInput(
                    current_password="wrong", new_password="a whole new passphrase"
                ),
                Actor(user_id=user.id),
            )

    async def test_change_password_rejects_reuse(self, users, sessions, hasher, clock) -> None:
        user = existing_user(hasher)
        await users.add(user)
        uc = ChangePasswordUseCase(users=users, sessions=sessions, hasher=hasher, clock=clock)
        with pytest.raises(errors.SamePasswordError):
            await uc.execute(
                dto.ChangePasswordInput(
                    current_password="correct horse battery",
                    new_password="correct horse battery",
                ),
                Actor(user_id=user.id),
            )


# ══════════════════════════════════════════════════════════════════════════
# Google
# ══════════════════════════════════════════════════════════════════════════


class TestGoogleLogin:
    @pytest.fixture
    def google(self) -> FakeGoogleProvider:
        return FakeGoogleProvider()

    @pytest.fixture
    def use_case(self, users, sessions, google, issuer, clock):
        return GoogleLoginUseCase(
            users=users, sessions=sessions, google=google, issuer=issuer, clock=clock
        )

    async def test_first_sign_in_creates_an_active_account(self, use_case, users) -> None:
        result = await use_case.execute(dto.GoogleLoginInput(id_token="tok", context=CTX), ANON)
        assert result.is_new_user
        assert result.user.email_verified  # Google already proved it
        assert not result.user.has_password

    async def test_second_sign_in_reuses_the_account(self, use_case, users) -> None:
        first = await use_case.execute(dto.GoogleLoginInput(id_token="tok", context=CTX), ANON)
        second = await use_case.execute(dto.GoogleLoginInput(id_token="tok", context=CTX), ANON)
        assert second.user.id == first.user.id
        assert not second.is_new_user

    async def test_links_to_an_existing_account_with_the_same_verified_email(
        self, use_case, users, hasher
    ) -> None:
        existing = existing_user(hasher)
        await users.add(existing)
        result = await use_case.execute(dto.GoogleLoginInput(id_token="tok", context=CTX), ANON)
        assert result.user.id == existing.id
        assert result.user.has_password  # the password survives linking

    async def test_unverified_provider_email_is_refused(self, use_case, google) -> None:
        """The account-takeover defence.

        Trusting an unverified provider address would let anyone who can create
        a Google account claiming an address take over the matching local one.
        """
        google.identity = type(google.identity)(
            subject="google-sub-123",
            email="priya@example.com",
            email_verified=False,
            full_name=None,
            picture=None,
            hosted_domain=None,
        )
        with pytest.raises(errors.OAuthEmailUnverifiedError):
            await use_case.execute(dto.GoogleLoginInput(id_token="tok", context=CTX), ANON)

    async def test_suspension_cannot_be_bypassed_by_switching_method(
        self, use_case, users, hasher
    ) -> None:
        existing = existing_user(hasher)
        existing.suspend(reason="fraud", by=None, now=NOW)
        await users.add(existing)
        with pytest.raises(errors.AccountSuspendedError):
            await use_case.execute(dto.GoogleLoginInput(id_token="tok", context=CTX), ANON)


# ══════════════════════════════════════════════════════════════════════════
# OTP
# ══════════════════════════════════════════════════════════════════════════


class TestOtpLogin:
    @pytest.fixture
    def otp(self) -> FakeOtpService:
        return FakeOtpService()

    @pytest.fixture
    def use_case(self, users, sessions, otp, issuer, clock):
        return VerifyOtpUseCase(users=users, sessions=sessions, otp=otp, issuer=issuer, clock=clock)

    async def test_verifying_a_new_number_registers_and_signs_in(
        self, use_case, otp, users
    ) -> None:
        from app.modules.auth.domain.value_objects import PhoneNumber

        challenge = await otp.issue(PhoneNumber("+919876543210"), purpose="login")
        result = await use_case.execute(
            dto.VerifyOtpInput(challenge_id=challenge.challenge_id, code="482913", context=CTX),
            ANON,
        )
        assert result.is_new_user
        assert result.user.phone_verified
        assert result.tokens.access_token

    async def test_a_wrong_code_is_refused(self, use_case, otp) -> None:
        from app.modules.auth.domain.value_objects import PhoneNumber

        challenge = await otp.issue(PhoneNumber("+919876543210"), purpose="login")
        with pytest.raises(errors.OtpInvalidError):
            await use_case.execute(
                dto.VerifyOtpInput(challenge_id=challenge.challenge_id, code="000000", context=CTX),
                ANON,
            )

    async def test_a_code_cannot_be_replayed(self, use_case, otp) -> None:
        from app.modules.auth.domain.value_objects import PhoneNumber

        challenge = await otp.issue(PhoneNumber("+919876543210"), purpose="login")
        await use_case.execute(
            dto.VerifyOtpInput(challenge_id=challenge.challenge_id, code="482913", context=CTX),
            ANON,
        )
        with pytest.raises(errors.OtpInvalidError):
            await use_case.execute(
                dto.VerifyOtpInput(challenge_id=challenge.challenge_id, code="482913", context=CTX),
                ANON,
            )


# ══════════════════════════════════════════════════════════════════════════
# Logout
# ══════════════════════════════════════════════════════════════════════════


class TestLogout:
    async def test_logout_revokes_the_family(self, users, sessions, hasher, issuer, clock) -> None:
        user = existing_user(hasher)
        await users.add(user)
        login = LoginUseCase(
            users=users, sessions=sessions, hasher=hasher, issuer=issuer, clock=clock
        )
        result = await login.execute(
            dto.LoginInput(
                email="priya@example.com", password="correct horse battery", context=CTX
            ),
            ANON,
        )

        uc = LogoutUseCase(sessions=sessions, users=users, clock=clock)
        count = await uc.execute(
            dto.LogoutInput(refresh_token=result.tokens.refresh_token), Actor(user_id=user.id)
        )
        assert count == 1
        assert all(s.is_revoked for s in sessions.sessions.values())

    async def test_logout_with_an_unknown_token_still_succeeds(
        self, users, sessions, clock
    ) -> None:
        # The caller's intent is "end my session"; that state is already true,
        # and an error would leave clients unsure whether to clear their tokens.
        uc = LogoutUseCase(sessions=sessions, users=users, clock=clock)
        assert await uc.execute(dto.LogoutInput(refresh_token="nonsense"), ANON) == 0

    async def test_logout_all_devices(self, users, sessions, hasher, issuer, clock) -> None:
        user = existing_user(hasher)
        await users.add(user)
        login = LoginUseCase(
            users=users, sessions=sessions, hasher=hasher, issuer=issuer, clock=clock
        )
        for _ in range(3):
            await login.execute(
                dto.LoginInput(
                    email="priya@example.com", password="correct horse battery", context=CTX
                ),
                ANON,
            )

        uc = LogoutUseCase(sessions=sessions, users=users, clock=clock)
        assert await uc.execute(dto.LogoutInput(all_devices=True), Actor(user_id=user.id)) == 3
