"""What the vendor use cases need from persistence."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.modules.auth.public import VendorAccess
from app.modules.vendor.domain.entities import Vendor

__all__ = ["VendorAccess", "VendorRepository"]


class VendorRepository(Protocol):
    async def get(self, vendor_id: uuid.UUID) -> Vendor | None: ...

    async def get_by_owner(self, user_id: uuid.UUID) -> Vendor | None:
        """One vendor account per user — a second would make "which one gets
        paid?" ambiguous at payout time."""
        ...

    async def add(self, vendor: Vendor) -> None: ...

    async def list_for_admin(
        self,
        *,
        status: str | None = None,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Vendor], int]: ...
