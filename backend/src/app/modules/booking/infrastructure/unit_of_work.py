"""The booking transaction scope.

Lives in infrastructure, not interface, because it *is* infrastructure — and
because the scheduled tasks need it too. A unit of work reachable only from the
HTTP layer would force every background job to import a router's dependencies.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.outbox import persist_events
from app.modules.booking.infrastructure.repositories import (
    SqlBookingRepository,
    SqlInvoiceNumberGenerator,
)
from app.modules.property.public import build_inventory_service, build_property_catalog


class BookingUow:
    """One transaction spanning bookings *and* inventory.

    The property adapters take the **same session**, which is the mechanism
    behind the module's central guarantee: the booking row and the inventory it
    holds are written together or not at all. Two sessions would mean two
    transactions and a window where a booking exists with no room behind it.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.bookings = SqlBookingRepository(session)
        self.invoice_numbers = SqlInvoiceNumberGenerator(session)
        # Built through the property module's published factories — booking
        # never names its concrete adapters.
        self.catalog = build_property_catalog(session)
        self.inventory = build_inventory_service(session)

    async def flush(self) -> None:
        await self.bookings.flush()
        # Events land in the same transaction as the state change.
        await persist_events(self.session, self.bookings.pending_events())

    async def commit(self) -> None:
        """For background jobs, which own their own transaction boundary."""
        await self.flush()
        await self.session.commit()

    def pending_events(self) -> list[Any]:
        return self.bookings.pending_events()
