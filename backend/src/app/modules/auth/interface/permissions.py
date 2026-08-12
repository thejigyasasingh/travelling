"""Route-level authorisation.

``RequirePermission`` answers **"may this kind of actor do this kind of
thing?"** — a capability question, answerable from the token alone, with no
database access.

It does **not** answer "is this *your* booking?". Ownership needs the row, and
only the use case has loaded it. Doing ownership checks here would mean
fetching the resource twice and, worse, would let the dependency's idea of
ownership drift from whatever the domain actually enforces. Keep the two
clearly separated:

    @router.post("/bookings/{id}/cancel",
                 dependencies=[Depends(RequirePermission(Permission.BOOKING_CANCEL_OWN))])
    async def cancel(...):
        ...  # the use case then checks that this booking belongs to the actor

The permission catalogue is expanded from roles in-process (see
``domain/rbac.py``), so this costs a frozenset lookup.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.errors import ForbiddenError
from app.core.logging import get_logger
from app.interface.api.deps import ActorDep
from app.modules.auth.domain.rbac import Permission, Role, has_permission, permissions_for
from app.shared.application.use_case import Actor

logger = get_logger(__name__)


class RequirePermission:
    """Require **all** listed permissions.

    ALL, not ANY. A handler that both reads and refunds a payment needs both;
    an ANY check would admit a read-only support agent to the refund path.
    Where ANY genuinely is the rule, say so with :class:`RequireAnyPermission`
    so that the looser check is visible at the call site.
    """

    def __init__(self, *permissions: Permission) -> None:
        if not permissions:  # pragma: no cover — guards a copy-paste mistake
            msg = "RequirePermission needs at least one permission"
            raise ValueError(msg)
        self.permissions = permissions

    def __call__(self, actor: ActorDep) -> Actor:
        if not has_permission(actor.roles, *self.permissions):
            missing = sorted(
                p.value for p in self.permissions if p not in permissions_for(actor.roles)
            )
            logger.info(
                "permission_denied",
                user_id=str(actor.user_id),
                required=missing,
                roles=sorted(actor.roles),
            )
            raise ForbiddenError(
                "You do not have permission to perform this action.",
                details={"required_permissions": missing},
            )
        return actor


class RequireAnyPermission:
    """Require at least one of the listed permissions.

    For endpoints that serve several audiences through one path — a booking
    detail readable by its owner, the vendor, or support. The handler then
    narrows what each may see.
    """

    def __init__(self, *permissions: Permission) -> None:
        self.permissions = permissions

    def __call__(self, actor: ActorDep) -> Actor:
        granted = permissions_for(actor.roles)
        if not any(p in granted for p in self.permissions):
            raise ForbiddenError(
                "You do not have permission to perform this action.",
                details={"required_any_of": sorted(p.value for p in self.permissions)},
            )
        return actor


class RequireRole:
    """Blunter than a permission check; use only where the role itself is the
    concept — an admin-only console, say. Prefer permissions everywhere else,
    because they survive a role being split in two."""

    def __init__(self, *roles: Role) -> None:
        self.roles = frozenset(r.value for r in roles)

    def __call__(self, actor: ActorDep) -> Actor:
        if not actor.roles.intersection(self.roles):
            raise ForbiddenError(
                "This action requires elevated permissions.",
                details={"required_roles": sorted(self.roles)},
            )
        return actor


def require_verified_email(actor: ActorDep) -> Actor:
    """Guard for actions needing a reachable address — booking, payouts.

    Deliberately **not** applied to sign-in. Blocking login until verification
    is a large drop-off for a marketplace: users sign up on mobile, never open
    the email, and never come back. Browsing and profile management work
    unverified; anything that will later need to send a confirmation or an
    invoice does not.

    Reads the ``evf`` claim from the token rather than the database, so it
    costs nothing on the request path. A user who has just verified still
    carries a stale ``false`` until their next refresh — which the client does
    immediately after verifying, precisely because of this.
    """
    if not actor.email_verified:
        raise ForbiddenError(
            "Please verify your email address to continue.",
            details={"code": "EMAIL_NOT_VERIFIED"},
        )
    return actor


VerifiedUserDep = Annotated[Actor, Depends(require_verified_email)]


# ── ready-made guards for the common cases ────────────────────────────────

RequireAdmin = RequireRole(Role.ADMIN, Role.SUPERADMIN)
RequireSupport = RequireRole(Role.SUPPORT, Role.ADMIN, Role.SUPERADMIN)
RequireVendor = RequireRole(Role.VENDOR, Role.VENDOR_STAFF, Role.ADMIN, Role.SUPERADMIN)

AdminDep = Annotated[Actor, Depends(RequireAdmin)]
SupportDep = Annotated[Actor, Depends(RequireSupport)]
VendorDep = Annotated[Actor, Depends(RequireVendor)]
CanGrantRolesDep = Annotated[Actor, Depends(RequirePermission(Permission.ROLE_GRANT_ANY))]
