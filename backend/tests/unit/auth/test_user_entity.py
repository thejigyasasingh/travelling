"""The User aggregate: lockout, verification, roles, credential invalidation.

Every rule here is security-relevant and none of it touches a database. That is
the payoff of keeping the domain framework-free — the whole lockout ladder is
exercised in milliseconds, including the 24-hour escalation, by moving a clock
that we own.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.auth.domain import errors
from app.modules.auth.domain.entities import (
    LOCKOUT_DURATIONS,
    LOCKOUT_THRESHOLD,
    User,
    UserStatus,
)
from app.modules.auth.domain.rbac import DEFAULT_ROLE, Permission, Role
from app.modules.auth.domain.value_objects import Email, PhoneNumber

pytestmark = pytest.mark.unit

NOW = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)


def make_user(**kw: object) -> User:
    defaults: dict[str, object] = {
        "email": Email.parse("priya@example.com"),
        "password_hash": "$argon2id$fake",
        "now": NOW,
    }
    return User.register(**{**defaults, **kw})  # type: ignore[arg-type]


class TestRegistration:
    def test_starts_pending_verification(self) -> None:
        user = make_user()
        assert user.status is UserStatus.PENDING_VERIFICATION
        assert not user.is_email_verified

    def test_gets_the_default_role_only(self) -> None:
        assert make_user().roles == frozenset({DEFAULT_ROLE})

    def test_records_a_registration_event(self) -> None:
        events = make_user().pull_events()
        assert [e.event_type for e in events] == ["auth.user.registered"]

    def test_events_are_drained_not_copied(self) -> None:
        # Draining is what makes double-publication impossible.
        user = make_user()
        assert user.pull_events()
        assert user.pull_events() == []

    def test_oauth_signup_has_no_password(self) -> None:
        # None, not "" — the type carries "cannot sign in with a password".
        user = User.register_via_oauth(
            email=Email.parse("priya@example.com"),
            provider_email_verified=True,
            full_name="Priya",
            avatar_url=None,
            now=NOW,
        )
        assert user.password_hash is None
        assert not user.has_password

    def test_oauth_signup_with_verified_email_is_active_immediately(self) -> None:
        # Google already proved the address; asking again is friction for
        # nothing.
        user = User.register_via_oauth(
            email=Email.parse("p@example.com"),
            provider_email_verified=True,
            full_name=None,
            avatar_url=None,
            now=NOW,
        )
        assert user.status is UserStatus.ACTIVE
        assert user.is_email_verified

    def test_oauth_signup_with_unverified_email_stays_pending(self) -> None:
        user = User.register_via_oauth(
            email=Email.parse("p@example.com"),
            provider_email_verified=False,
            full_name=None,
            avatar_url=None,
            now=NOW,
        )
        assert user.status is UserStatus.PENDING_VERIFICATION

    def test_phone_signup_is_active_with_a_verified_phone(self) -> None:
        user = User.register_via_phone(
            phone=PhoneNumber("+919876543210"),
            email=Email.parse("919876543210@phone.invalid.test"),
            now=NOW,
        )
        assert user.is_phone_verified
        assert user.status is UserStatus.ACTIVE


class TestLockout:
    """The brute-force ladder. See LOCKOUT_DURATIONS for the policy."""

    def test_below_the_threshold_nothing_happens(self) -> None:
        # A user who mistypes twice should feel nothing at all.
        user = make_user()
        for _ in range(LOCKOUT_THRESHOLD - 1):
            user.record_failed_login(NOW)
        assert not user.is_locked(NOW)

    def test_locks_at_the_threshold(self) -> None:
        user = make_user()
        for _ in range(LOCKOUT_THRESHOLD):
            user.record_failed_login(NOW)
        assert user.is_locked(NOW)
        assert user.lock_remaining_seconds(NOW) == LOCKOUT_DURATIONS[0]

    def test_lockout_escalates_and_does_not_reset_on_expiry(self) -> None:
        """The critical property.

        If `lockout_level` reset when the lock expired, an attacker would wait
        out each 60-second lock and get five fresh attempts forever — the
        escalation would never bite and the ladder would be decorative.
        """
        user = make_user()
        moment = NOW

        for expected in LOCKOUT_DURATIONS:
            for _ in range(LOCKOUT_THRESHOLD):
                user.record_failed_login(moment)
            assert user.lock_remaining_seconds(moment) == expected
            # Wait out the lock, exactly as an attacker would.
            moment = moment + timedelta(seconds=expected + 1)
            assert not user.is_locked(moment)

    def test_escalation_caps_at_the_longest_duration(self) -> None:
        user = make_user()
        moment = NOW
        for _ in range(len(LOCKOUT_DURATIONS) + 3):
            for _ in range(LOCKOUT_THRESHOLD):
                user.record_failed_login(moment)
            moment = moment + timedelta(seconds=LOCKOUT_DURATIONS[-1] + 1)
        for _ in range(LOCKOUT_THRESHOLD):
            user.record_failed_login(moment)
        assert user.lock_remaining_seconds(moment) == LOCKOUT_DURATIONS[-1]

    def test_locked_account_refuses_login_before_any_hashing(self) -> None:
        user = make_user()
        for _ in range(LOCKOUT_THRESHOLD):
            user.record_failed_login(NOW)
        with pytest.raises(errors.AccountLockedError) as exc:
            user.assert_can_attempt_login(NOW)
        assert exc.value.retry_after_seconds > 0

    def test_successful_login_clears_the_whole_ladder(self) -> None:
        # Knowing the password means the earlier failures were typos.
        user = make_user()
        for _ in range(LOCKOUT_THRESHOLD * 2):
            user.record_failed_login(NOW)
        user.record_successful_login(now=NOW, method="password", session_id=uuid.uuid4())
        assert user.lockout_level == 0
        assert user.locked_until is None
        assert user.failed_login_attempts == 0

    def test_lock_emits_a_security_event(self) -> None:
        user = make_user()
        user.pull_events()
        for _ in range(LOCKOUT_THRESHOLD):
            user.record_failed_login(NOW)
        types = [e.event_type for e in user.pull_events()]
        assert "auth.account.locked" in types
        assert types.count("auth.login.failed") == LOCKOUT_THRESHOLD

    def test_password_reset_unlocks(self) -> None:
        # Reset is the documented recovery path; leaving the lock would strand
        # the legitimate user.
        user = make_user()
        for _ in range(LOCKOUT_THRESHOLD):
            user.record_failed_login(NOW)
        user.set_password("$argon2id$new", now=NOW, via_reset=True)
        assert not user.is_locked(NOW)


class TestLoginGuards:
    def test_suspended_looks_like_bad_credentials(self) -> None:
        # Telling an unauthenticated caller "this account is suspended"
        # confirms the account exists.
        user = make_user()
        user.suspend(reason="fraud", by=None, now=NOW)
        with pytest.raises(errors.InvalidCredentialsError):
            user.assert_can_attempt_login(NOW)

    def test_deactivated_looks_like_bad_credentials(self) -> None:
        user = make_user()
        user.deactivate()
        with pytest.raises(errors.InvalidCredentialsError):
            user.assert_can_attempt_login(NOW)

    def test_pending_verification_may_still_sign_in(self) -> None:
        # Blocking login until verification is a large marketplace drop-off;
        # booking is what requires a reachable address.
        make_user().assert_can_attempt_login(NOW)

    def test_signing_in_reverses_a_deactivation(self) -> None:
        user = make_user()
        user.verify_email(NOW)
        user.deactivate()
        user.record_successful_login(now=NOW, method="password", session_id=uuid.uuid4())
        assert user.status is UserStatus.ACTIVE


class TestVerification:
    def test_verifying_activates_the_account(self) -> None:
        user = make_user()
        user.verify_email(NOW)
        assert user.is_email_verified
        assert user.status is UserStatus.ACTIVE

    def test_verifying_twice_is_idempotent_and_silent(self) -> None:
        # Mail clients pre-fetch links and users double-click.
        user = make_user()
        user.verify_email(NOW)
        user.pull_events()
        user.verify_email(NOW + timedelta(hours=1))
        assert user.pull_events() == []

    def test_require_verified_email_raises_when_unverified(self) -> None:
        with pytest.raises(errors.EmailNotVerifiedError):
            make_user().require_verified_email()

    def test_suspension_survives_verification(self) -> None:
        user = make_user()
        user.suspend(reason="fraud", by=None, now=NOW)
        user.verify_email(NOW)
        assert user.status is UserStatus.SUSPENDED


class TestCredentialInvalidation:
    """`password_changed_at` is the cutoff that makes "changing your password
    signs you out everywhere" work without hunting down rows."""

    def test_credentials_issued_before_a_change_are_stale(self) -> None:
        user = make_user()
        issued = NOW
        user.set_password("$argon2id$new", now=NOW + timedelta(minutes=5), via_reset=False)
        assert user.credentials_issued_before(issued)

    def test_credentials_issued_after_a_change_are_fine(self) -> None:
        user = make_user()
        user.set_password("$argon2id$new", now=NOW, via_reset=False)
        assert not user.credentials_issued_before(NOW + timedelta(minutes=5))

    def test_no_change_recorded_means_nothing_is_stale(self) -> None:
        user = User(email=Email.parse("a@b.com"), password_hash="x")
        assert not user.credentials_issued_before(NOW)

    def test_oauth_account_cannot_change_password(self) -> None:
        user = User.register_via_oauth(
            email=Email.parse("a@b.com"),
            provider_email_verified=True,
            full_name=None,
            avatar_url=None,
            now=NOW,
        )
        with pytest.raises(errors.PasswordNotSetError):
            user.assert_can_change_password()


class TestRoles:
    def test_granting_records_who_did_it(self) -> None:
        user = make_user()
        user.pull_events()
        admin = uuid.uuid4()
        user.grant_roles(frozenset({Role.VENDOR}), by=admin)
        event = user.pull_events()[0]
        assert event.event_type == "auth.roles.changed"
        assert event.to_payload()["changed_by"] == str(admin)

    def test_granting_an_existing_role_is_a_no_op(self) -> None:
        user = make_user()
        user.pull_events()
        user.grant_roles(frozenset({DEFAULT_ROLE}), by=None)
        assert user.pull_events() == []

    def test_the_default_role_cannot_be_revoked(self) -> None:
        # A user with no roles can sign in and then get 403 on every request,
        # with nothing in the UI explaining why.
        user = make_user()
        user.revoke_roles(frozenset({DEFAULT_ROLE}), by=None)
        assert DEFAULT_ROLE in user.roles

    def test_revoking_removes_the_capability(self) -> None:
        user = make_user()
        user.grant_roles(frozenset({Role.VENDOR}), by=None)
        assert user.has_permission(Permission.PROPERTY_CREATE_VENDOR)
        user.revoke_roles(frozenset({Role.VENDOR}), by=None)
        assert not user.has_permission(Permission.PROPERTY_CREATE_VENDOR)

    def test_require_permission_raises_with_what_is_missing(self) -> None:
        with pytest.raises(errors.MissingPermissionError) as exc:
            make_user().require_permission(Permission.PAYMENT_REFUND_ANY)
        assert "payment:refund:any" in exc.value.details["required_permissions"]
