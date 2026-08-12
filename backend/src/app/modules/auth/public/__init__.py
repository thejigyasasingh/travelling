"""The auth module's **published contract**.

Other modules import from here and from nowhere else inside
``app.modules.auth`` — enforced by a contract in ``.importlinter``.

Narrower than the property and booking contracts on purpose: auth owns
credentials, sessions and roles, and almost nothing outside it has any business
touching those. The single published operation joins a newly registered vendor
to the identity that owns it.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.public.contract import VendorAccess, VendorOwnershipConflictError


def build_vendor_access(session: AsyncSession) -> VendorAccess:
    """Construct the adapter against the caller's session, so the grant and the
    vendor row it describes commit together."""
    from app.modules.auth.public.adapters import SqlVendorAccess

    return SqlVendorAccess(session)


__all__ = [
    "VendorAccess",
    "VendorOwnershipConflictError",
    "build_vendor_access",
]
