"""Role and permission resolution.

These tests are the specification for who can do what. If one fails, either
someone changed a security policy, or someone made a mistake — and the diff
tells you which.
"""

from __future__ import annotations

import pytest

from app.modules.auth.domain.rbac import (
    DEFAULT_ROLE,
    ELEVATED_ROLES,
    ROLE_PERMISSIONS,
    Permission,
    Role,
    assignable_roles,
    has_permission,
    permissions_for,
)

pytestmark = pytest.mark.unit


class TestInheritance:
    def test_every_role_resolves(self) -> None:
        # Catches a cycle or a missing entry in _INHERITS at import time.
        assert set(ROLE_PERMISSIONS) == set(Role)

    def test_vendor_inherits_traveler(self) -> None:
        # A vendor is also a customer — they book stays too.
        assert Permission.BOOKING_CREATE_OWN in ROLE_PERMISSIONS[Role.VENDOR]

    def test_vendor_inherits_vendor_staff(self) -> None:
        assert Permission.PROPERTY_UPDATE_VENDOR in ROLE_PERMISSIONS[Role.VENDOR]

    def test_admin_inherits_support_and_vendor(self) -> None:
        admin = ROLE_PERMISSIONS[Role.ADMIN]
        assert ROLE_PERMISSIONS[Role.SUPPORT] <= admin
        assert ROLE_PERMISSIONS[Role.VENDOR] <= admin

    def test_superadmin_is_a_strict_superset_of_admin(self) -> None:
        assert ROLE_PERMISSIONS[Role.ADMIN] < ROLE_PERMISSIONS[Role.SUPERADMIN]


class TestPrivilegeBoundaries:
    """The checks that stop privilege escalation. Each corresponds to a real
    attack, so a change here needs a security conversation, not a code review."""

    def test_only_superadmin_can_grant_roles(self) -> None:
        # An admin who can grant roles can make themselves a superadmin, which
        # erases the distinction between the two entirely.
        for role in Role:
            granted = Permission.ROLE_GRANT_ANY in ROLE_PERMISSIONS[role]
            assert granted == (role is Role.SUPERADMIN), f"{role} unexpectedly grants roles"

    def test_only_superadmin_can_impersonate(self) -> None:
        holders = [r for r in Role if Permission.USER_IMPERSONATE_ANY in ROLE_PERMISSIONS[r]]
        assert holders == [Role.SUPERADMIN]

    def test_traveler_cannot_touch_other_peoples_data(self) -> None:
        traveler = ROLE_PERMISSIONS[Role.TRAVELER]
        forbidden = {
            Permission.BOOKING_READ_ANY,
            Permission.BOOKING_CANCEL_ANY,
            Permission.USER_READ_ANY,
            Permission.PAYMENT_REFUND_ANY,
            Permission.PROPERTY_PUBLISH_ANY,
        }
        assert not (traveler & forbidden)

    def test_vendor_is_scoped_to_its_own_inventory(self) -> None:
        # A vendor must never see another vendor's bookings or payments.
        vendor = ROLE_PERMISSIONS[Role.VENDOR]
        assert Permission.BOOKING_READ_VENDOR in vendor
        assert Permission.BOOKING_READ_ANY not in vendor
        assert Permission.PAYMENT_READ_ANY not in vendor

    def test_support_cannot_refund_or_approve_payouts(self) -> None:
        # Support handles a high volume of tickets; moving money needs admin.
        support = ROLE_PERMISSIONS[Role.SUPPORT]
        assert Permission.PAYMENT_READ_ANY in support
        assert Permission.PAYMENT_REFUND_ANY not in support
        assert Permission.PAYOUT_APPROVE_ANY not in support

    def test_system_role_has_no_permissions(self) -> None:
        # It exists to label background jobs in audit logs, not to grant access.
        assert ROLE_PERMISSIONS[Role.SYSTEM] == frozenset()

    def test_system_role_is_not_assignable(self) -> None:
        # A human holding it would make "who did this?" unanswerable.
        assert Role.SYSTEM not in assignable_roles()


class TestResolution:
    def test_union_across_roles(self) -> None:
        granted = permissions_for({"traveler", "vendor"})
        assert Permission.BOOKING_CREATE_OWN in granted
        assert Permission.PROPERTY_CREATE_VENDOR in granted

    def test_unknown_role_is_ignored_not_fatal(self) -> None:
        # A token issued before a role was renamed must grant less, not 500.
        granted = permissions_for({"traveler", "wizard"})
        assert Permission.BOOKING_CREATE_OWN in granted

    def test_empty_roles_grant_nothing(self) -> None:
        assert permissions_for(set()) == frozenset()

    def test_has_permission_requires_all_not_any(self) -> None:
        # ALL is the rule; an ANY check would let a read-only support agent
        # through a handler that also refunds.
        roles = {"support"}
        assert has_permission(roles, Permission.PAYMENT_READ_ANY)
        assert not has_permission(roles, Permission.PAYMENT_READ_ANY, Permission.PAYMENT_REFUND_ANY)

    def test_default_role_can_do_the_core_journey(self) -> None:
        # A brand-new signup must be able to search, book and pay with no
        # further grants.
        granted = permissions_for({DEFAULT_ROLE.value})
        for required in (
            Permission.PROPERTY_READ_ANY,
            Permission.BOOKING_CREATE_OWN,
            Permission.BOOKING_READ_OWN,
            Permission.PAYMENT_READ_OWN,
        ):
            assert required in granted


class TestCatalogue:
    def test_every_permission_is_resource_action_scope(self) -> None:
        # The scope suffix is what stops "can cancel a booking" from silently
        # meaning "can cancel anyone's booking".
        for permission in Permission:
            resource, action, scope = permission.value.split(":")
            assert resource and action
            assert scope in {"own", "vendor", "any"}, permission.value

    def test_no_permission_is_orphaned(self) -> None:
        # A permission nobody holds is either a missing grant or dead code.
        held = set().union(*ROLE_PERMISSIONS.values())
        assert set(Permission) - held == set()

    def test_elevated_roles_are_the_staff_roles(self) -> None:
        assert {Role.SUPPORT, Role.ADMIN, Role.SUPERADMIN} == ELEVATED_ROLES
