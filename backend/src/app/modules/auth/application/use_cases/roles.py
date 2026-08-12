"""Granting and revoking roles, and reading your own profile.

Role changes are the highest-privilege operation in the system — the one that
lets an attacker turn a foothold into ownership — so three rules apply:

**Only ``ROLE_GRANT_ANY`` may do it**, which by the catalogue in ``rbac.py``
means superadmin alone. An admin who can grant roles can make themselves a
superadmin, which makes the distinction meaningless.

**Nobody may change their own roles.** Self-grant is the classic escalation
path: compromise any account that can grant, then grant it everything. The
check costs one comparison.

**Every change is an audited event** carrying who did it. "Who made this person
an admin?" is the first question after an incident, and it needs an answer that
does not depend on someone having enabled query logging.

Role changes do **not** take effect instantly. The access token carries roles
and lives up to 15 minutes, so a revocation lands on the next refresh. That is
the documented cost of keeping authorisation out of the database on the request
path; where it is unacceptable, revoke the sessions too — which this does.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.clock import Clock
from app.core.logging import get_logger
from app.modules.auth.application.dto import ChangeRolesInput, UserProfile
from app.modules.auth.application.ports import SessionRepository, UserRepository
from app.modules.auth.application.services import to_profile
from app.modules.auth.domain import errors
from app.modules.auth.domain.rbac import (
    ELEVATED_ROLES,
    Permission,
    Role,
    assignable_roles,
    has_permission,
)
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)


@dataclass(slots=True)
class ChangeRolesUseCase:
    users: UserRepository
    sessions: SessionRepository
    clock: Clock

    async def execute(self, data: ChangeRolesInput, actor: Actor) -> UserProfile:
        if actor.user_id is None:  # pragma: no cover — route requires auth
            raise errors.InvalidCredentialsError

        # Re-checked here even though the route already gated on it. The route
        # guard protects the HTTP surface; this protects the use case, which a
        # CLI command or a future admin task will also call.
        if not _actor_may_grant(actor):
            raise errors.MissingPermissionError(Permission.ROLE_GRANT_ANY.value)

        if data.user_id == actor.user_id:
            raise errors.MissingPermissionError(Permission.ROLE_GRANT_ANY.value)

        grant = _parse_roles(data.grant)
        revoke = _parse_roles(data.revoke)

        user = await self.users.get(data.user_id)
        if user is None:
            raise EntityNotFoundError("User", data.user_id)

        user.grant_roles(grant, by=actor.user_id)
        user.revoke_roles(revoke, by=actor.user_id)

        if revoke or (grant & ELEVATED_ROLES):
            # A revocation must bite now, not in fifteen minutes. Granting an
            # elevated role also forces a re-login so the new capability is
            # obtained through a fresh, logged authentication rather than
            # appearing mid-session.
            count = await self.sessions.revoke_all_for_user(
                user.id, now=self.clock.now(), reason="roles_changed"
            )
            logger.info("sessions_revoked_after_role_change", user_id=str(user.id), count=count)

        logger.warning(  # WARNING: privilege changes should be visible in log search
            "roles_changed",
            user_id=str(user.id),
            granted=sorted(r.value for r in grant),
            revoked=sorted(r.value for r in revoke),
            changed_by=str(actor.user_id),
        )
        return to_profile(user)


@dataclass(slots=True)
class GetProfileUseCase:
    """``GET /auth/me``. The client's source of truth after a refresh.

    Reads from the database rather than decoding the caller's token, because
    the token is a snapshot: a role granted or an email verified two minutes
    ago will not be in it.
    """

    users: UserRepository

    async def execute(self, _: None, actor: Actor) -> UserProfile:
        if actor.user_id is None:  # pragma: no cover
            raise errors.InvalidCredentialsError

        user = await self.users.get(actor.user_id)
        if user is None:
            raise EntityNotFoundError("User", actor.user_id)
        return to_profile(user)


def _actor_may_grant(actor: Actor) -> bool:
    return has_permission(frozenset(actor.roles), Permission.ROLE_GRANT_ANY)


def _parse_roles(names: list[str]) -> frozenset[Role]:
    """Unknown or non-assignable names are rejected outright.

    Silently ignoring them would let a typo'd grant report success while
    changing nothing, and the operator would only find out when the user
    complains.
    """
    parsed: set[Role] = set()
    allowed = assignable_roles()
    for name in names:
        try:
            role = Role(name)
        except ValueError as exc:
            raise errors.RoleNotAssignableError(name) from exc
        if role not in allowed:
            raise errors.RoleNotAssignableError(name)
        parsed.add(role)
    return frozenset(parsed)
