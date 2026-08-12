"""The payment transaction scope.

In infrastructure rather than interface because the scheduled jobs — refund
execution, capture, reconciliation, webhook replay — need it as much as the
routes do, and a unit of work reachable only from HTTP would force every task
to import a router's dependencies.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.outbox import persist_events
from app.modules.booking.public import build_booking_payment_service
from app.modules.payment.infrastructure.repositories import (
    SqlPaymentRepository,
    SqlWebhookEventStore,
)


class PaymentUow:
    """One transaction spanning payments, the ledger and the booking it pays for.

    The booking service is built on the **same session**. That is the whole
    point: capturing money and confirming the booking commit together, or
    neither does. Two sessions would give a window where the money is taken and
    the booking is not confirmed — the one failure mode a payments module exists
    to prevent.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.payments = SqlPaymentRepository(session)
        self.events = SqlWebhookEventStore(session)
        # Through booking's published factory — payment never names booking's
        # concrete adapters, and `.importlinter` enforces it.
        self.bookings = build_booking_payment_service(session)

    async def flush(self) -> None:
        await self.payments.flush()
        # Events land in the same transaction as the state they describe, so a
        # captured payment can never exist without its event.
        await persist_events(self.session, self.payments.pending_events())

    async def commit(self) -> None:
        """For background jobs, which own their own transaction boundary."""
        await self.flush()
        await self.session.commit()

    def pending_events(self) -> list[Any]:
        return self.payments.pending_events()
