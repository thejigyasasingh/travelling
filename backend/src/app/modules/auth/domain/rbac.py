"""Roles and permissions.

**Role definitions live in code; role *assignments* live in the database.**

That split is the central decision here, and it is deliberate:

* What a role *can do* is a security policy. In code it is version-controlled,
  code-reviewed, diffable, and identical in every environment. As database
  rows it is mutable at 3am by anyone with a psql prompt, drifts between
  staging and production, and has no audit trail worth the name.
* Who *has* a role is operational data that changes constantly — support
  promotes a vendor, an admin is offboarded — and belongs in a table.

The consequence that makes this worth it: **authorisation needs no database
query.** The access token carries the user's roles; permissions are resolved
from this in-process map. At a million users that is the difference between
zero and one Postgres round-trip on every authenticated request.

The rows in `roles` and `permissions` are a *projection* of this file, written
by a migration, so an admin UI can list them and a foreign key can reference
them. This module stays the source of truth.

**Permission naming**: ``resource:action:scope``.

* ``scope = own``  — only rows the actor owns
* ``scope = vendor`` — rows belonging to the actor's vendor
* ``scope = any`` — everything

The scope suffix is what stops "can cancel a booking" from quietly meaning
"can cancel *anyone's* booking". Ownership itself is checked in the domain,
which is the only place that has the row loaded; this grants the *capability*.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class Role(StrEnum):
    """Every role in the system. Adding one is a code change, by design."""

    TRAVELER = "traveler"
    VENDOR = "vendor"
    VENDOR_STAFF = "vendor_staff"
    SUPPORT = "support"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"
    #: Background jobs and internal callers. Never assignable to a human —
    #: `assignable_roles()` excludes it so it cannot be granted through the API.
    SYSTEM = "system"


class Permission(StrEnum):
    # ── profile ──────────────────────────────────────────────────────────
    PROFILE_READ_OWN = "profile:read:own"
    PROFILE_UPDATE_OWN = "profile:update:own"
    PROFILE_DELETE_OWN = "profile:delete:own"
    USER_READ_ANY = "user:read:any"
    USER_SUSPEND_ANY = "user:suspend:any"
    USER_IMPERSONATE_ANY = "user:impersonate:any"

    # ── properties ───────────────────────────────────────────────────────
    #: The **public** catalogue. Every traveller holds this, because browsing
    #: published listings is what the site is for. It does not mean "read any
    #: property in any state" — see `PROPERTY_READ_INTERNAL`.
    PROPERTY_READ_ANY = "property:read:any"
    #: Every listing whatever its status: drafts, rejected, suspended,
    #: soft-deleted, with the vendor behind each one.
    #:
    #: A separate permission because the admin listing was guarded by
    #: `PROPERTY_READ_ANY` — which travellers hold — so any signed-in visitor
    #: could enumerate every property on the platform including ones hosts had
    #: taken down, with the rejection reasons attached. One overloaded name,
    #: two very different meanings.
    #:
    #: The distinguishing part is the **action**, not the scope. Both read
    #: across all vendors, so both are `:any`; `read_internal` is a different
    #: verb from `read` because it returns a different record. Spelling it
    #: `property:read:admin` would put a *role* where the scope goes and
    #: quietly break the `own | vendor | any` vocabulary the whole catalogue
    #: relies on.
    PROPERTY_READ_INTERNAL = "property:read_internal:any"
    PROPERTY_CREATE_VENDOR = "property:create:vendor"
    PROPERTY_UPDATE_VENDOR = "property:update:vendor"
    PROPERTY_DELETE_VENDOR = "property:delete:vendor"
    PROPERTY_PUBLISH_ANY = "property:publish:any"

    # ── bookings ─────────────────────────────────────────────────────────
    BOOKING_CREATE_OWN = "booking:create:own"
    BOOKING_READ_OWN = "booking:read:own"
    BOOKING_CANCEL_OWN = "booking:cancel:own"
    BOOKING_READ_VENDOR = "booking:read:vendor"
    BOOKING_CANCEL_VENDOR = "booking:cancel:vendor"
    BOOKING_READ_ANY = "booking:read:any"
    BOOKING_CANCEL_ANY = "booking:cancel:any"

    # ── payments ─────────────────────────────────────────────────────────
    PAYMENT_READ_OWN = "payment:read:own"
    PAYMENT_READ_VENDOR = "payment:read:vendor"
    PAYMENT_READ_ANY = "payment:read:any"
    PAYMENT_REFUND_ANY = "payment:refund:any"
    PAYOUT_READ_VENDOR = "payout:read:vendor"
    PAYOUT_APPROVE_ANY = "payout:approve:any"

    # ── reviews ──────────────────────────────────────────────────────────
    REVIEW_CREATE_OWN = "review:create:own"
    REVIEW_UPDATE_OWN = "review:update:own"
    REVIEW_RESPOND_VENDOR = "review:respond:vendor"
    REVIEW_MODERATE_ANY = "review:moderate:any"

    # ── support ──────────────────────────────────────────────────────────
    TICKET_CREATE_OWN = "ticket:create:own"
    TICKET_READ_OWN = "ticket:read:own"
    TICKET_READ_ANY = "ticket:read:any"
    TICKET_RESOLVE_ANY = "ticket:resolve:any"

    # ── platform ─────────────────────────────────────────────────────────
    VENDOR_APPROVE_ANY = "vendor:approve:any"
    COUPON_MANAGE_ANY = "coupon:manage:any"
    ROLE_GRANT_ANY = "role:grant:any"
    SETTINGS_MANAGE_ANY = "settings:manage:any"
    AUDIT_READ_ANY = "audit:read:any"


# ══════════════════════════════════════════════════════════════════════════
# Role → permission
#
# Written as *direct* grants plus explicit inheritance rather than one flat
# list per role. Inheritance is what keeps "support can do everything a
# traveler can" true after someone adds a new traveler permission six months
# from now and forgets to copy it.
# ══════════════════════════════════════════════════════════════════════════

_DIRECT_GRANTS: Final[dict[Role, frozenset[Permission]]] = {
    Role.TRAVELER: frozenset(
        {
            Permission.PROFILE_READ_OWN,
            Permission.PROFILE_UPDATE_OWN,
            Permission.PROFILE_DELETE_OWN,
            Permission.PROPERTY_READ_ANY,
            Permission.BOOKING_CREATE_OWN,
            Permission.BOOKING_READ_OWN,
            Permission.BOOKING_CANCEL_OWN,
            Permission.PAYMENT_READ_OWN,
            Permission.REVIEW_CREATE_OWN,
            Permission.REVIEW_UPDATE_OWN,
            Permission.TICKET_CREATE_OWN,
            Permission.TICKET_READ_OWN,
        }
    ),
    Role.VENDOR_STAFF: frozenset(
        {
            Permission.PROPERTY_UPDATE_VENDOR,
            Permission.BOOKING_READ_VENDOR,
            Permission.REVIEW_RESPOND_VENDOR,
        }
    ),
    Role.VENDOR: frozenset(
        {
            Permission.PROPERTY_CREATE_VENDOR,
            Permission.PROPERTY_DELETE_VENDOR,
            Permission.BOOKING_CANCEL_VENDOR,
            Permission.PAYMENT_READ_VENDOR,
            Permission.PAYOUT_READ_VENDOR,
        }
    ),
    Role.SUPPORT: frozenset(
        {
            Permission.USER_READ_ANY,
            # Support answers "where has my host's listing gone", which needs
            # the unpublished ones.
            Permission.PROPERTY_READ_INTERNAL,
            Permission.BOOKING_READ_ANY,
            Permission.BOOKING_CANCEL_ANY,
            Permission.PAYMENT_READ_ANY,
            Permission.TICKET_READ_ANY,
            Permission.TICKET_RESOLVE_ANY,
            Permission.REVIEW_MODERATE_ANY,
        }
    ),
    Role.ADMIN: frozenset(
        {
            Permission.USER_SUSPEND_ANY,
            Permission.PROPERTY_PUBLISH_ANY,
            Permission.PAYMENT_REFUND_ANY,
            Permission.PAYOUT_APPROVE_ANY,
            Permission.VENDOR_APPROVE_ANY,
            Permission.COUPON_MANAGE_ANY,
            Permission.AUDIT_READ_ANY,
        }
    ),
    Role.SUPERADMIN: frozenset(
        {
            # Kept to the two genuinely irreversible capabilities rather than
            # "everything", so that a compromised admin account still cannot
            # grant itself more, and impersonation has exactly one holder.
            Permission.ROLE_GRANT_ANY,
            Permission.SETTINGS_MANAGE_ANY,
            Permission.USER_IMPERSONATE_ANY,
        }
    ),
    Role.SYSTEM: frozenset(),
}

#: Each role also receives everything its parents have.
_INHERITS: Final[dict[Role, tuple[Role, ...]]] = {
    Role.TRAVELER: (),
    Role.VENDOR_STAFF: (Role.TRAVELER,),
    Role.VENDOR: (Role.VENDOR_STAFF,),
    Role.SUPPORT: (Role.TRAVELER,),
    Role.ADMIN: (Role.SUPPORT, Role.VENDOR),
    Role.SUPERADMIN: (Role.ADMIN,),
    Role.SYSTEM: (),
}


def _resolve(role: Role, _seen: frozenset[Role] = frozenset()) -> frozenset[Permission]:
    if role in _seen:  # pragma: no cover — guards a future editing mistake
        msg = f"Cycle in role inheritance at {role}"
        raise ValueError(msg)
    seen = _seen | {role}
    permissions = set(_DIRECT_GRANTS[role])
    for parent in _INHERITS[role]:
        permissions |= _resolve(parent, seen)
    return frozenset(permissions)


#: Fully expanded, computed once at import. Lookup is a frozenset hit.
ROLE_PERMISSIONS: Final[dict[Role, frozenset[Permission]]] = {role: _resolve(role) for role in Role}


def permissions_for(roles: frozenset[str] | set[str] | list[str]) -> frozenset[Permission]:
    """Union of every permission the given roles grant.

    Unknown role strings are ignored rather than raising. A token issued
    before a role was renamed must not 500 — it should simply grant less,
    which fails safe.
    """
    granted: set[Permission] = set()
    for raw in roles:
        try:
            granted |= ROLE_PERMISSIONS[Role(raw)]
        except ValueError:
            continue
    return frozenset(granted)


def has_permission(roles: frozenset[str] | set[str], *required: Permission) -> bool:
    """True if the roles grant **every** required permission.

    ALL, not ANY. A handler that needs to both read and refund a payment needs
    both; an ANY check would let a read-only support agent through.
    """
    granted = permissions_for(roles)
    return all(permission in granted for permission in required)


def assignable_roles() -> frozenset[Role]:
    """Roles a human may be granted through the API.

    ``SYSTEM`` is excluded because it identifies background jobs in audit
    logs; a human holding it would make "who did this?" unanswerable.
    """
    return frozenset(Role) - {Role.SYSTEM}


DEFAULT_ROLE: Final = Role.TRAVELER
#: Roles that make an account privileged. Used to require re-authentication
#: for sensitive actions and to alert on grants.
ELEVATED_ROLES: Final = frozenset({Role.SUPPORT, Role.ADMIN, Role.SUPERADMIN})
