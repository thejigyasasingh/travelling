"""Implementation of the published auth contract."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.auth.domain.rbac import Role
from app.modules.auth.public.contract import VendorOwnershipConflictError

logger = get_logger(__name__)

#: Conditional UPDATE rather than read-then-write. Two concurrent registrations
#: for the same user — a double tap on a slow connection — would both pass a
#: prior check and the second would clobber the first. The predicate makes the
#: second one a no-op instead.
#:
#: ``vendor_id = :vendor_id`` in the WHERE clause is what makes a replay
#: succeed silently while a *different* vendor updates nothing, which is how
#: the conflict below is detected.
_LINK_SQL = text(
    """
    UPDATE users
       SET vendor_id = :vendor_id,
           updated_at = now()
     WHERE id = :user_id
       AND (vendor_id IS NULL OR vendor_id = :vendor_id)
    """
)

#: The join table is the audited source of truth; a trigger from migration 0002
#: mirrors it onto ``users.roles``, which is what login reads. Writing only here
#: keeps that single direction intact.
#:
#: ``granted_by`` stays NULL: nobody granted this, registering did.
_ROLE_SQL = text(
    """
    INSERT INTO user_roles (id, user_id, role_name, granted_at)
    VALUES (gen_random_uuid(), :user_id, :role, now())
    ON CONFLICT ON CONSTRAINT uq_user_roles_user_role DO NOTHING
    """
)


@dataclass(slots=True)
class SqlVendorAccess:
    """Implements :class:`app.modules.auth.public.contract.VendorAccess`."""

    session: AsyncSession

    async def grant(self, *, user_id: uuid.UUID, vendor_id: uuid.UUID) -> None:
        result = cast(
            "CursorResult[Any]",
            await self.session.execute(_LINK_SQL, {"user_id": user_id, "vendor_id": vendor_id}),
        )
        if result.rowcount == 0:
            # Either the user does not exist — impossible, the caller
            # authenticated as them — or they already own a different vendor.
            raise VendorOwnershipConflictError(str(user_id))

        await self.session.execute(_ROLE_SQL, {"user_id": user_id, "role": Role.VENDOR.value})
        logger.info("vendor_access_granted", user_id=str(user_id), vendor_id=str(vendor_id))
