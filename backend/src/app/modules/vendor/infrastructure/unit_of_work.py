"""The vendor transaction scope."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.outbox import persist_events
from app.modules.auth.public import build_vendor_access
from app.modules.vendor.infrastructure.repositories import SqlVendorRepository


class VendorUow:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.vendors = SqlVendorRepository(session)
        # Same session as the vendor row, so registering and gaining access to
        # the portal are one atomic fact.
        self.access = build_vendor_access(session)

    async def flush(self) -> None:
        await self.vendors.flush()
        await persist_events(self.session, self.vendors.pending_events())

    async def commit(self) -> None:
        await self.flush()
        await self.session.commit()

    def pending_events(self) -> list[Any]:
        return self.vendors.pending_events()
