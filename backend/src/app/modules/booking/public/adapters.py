"""Implementation of the booking module's published contract."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock, SystemClock
from app.core.logging import get_logger
from app.core.types.date_range import DateRange
from app.core.types.money import Money
from app.modules.booking.application.dto import ConfirmBookingInput
from app.modules.booking.application.use_cases.lifecycle import ConfirmBookingUseCase
from app.modules.booking.domain.value_objects import BookingStatus
from app.modules.booking.infrastructure.repositories import (
    SqlBookingRepository,
    SqlInvoiceNumberGenerator,
)
from app.modules.booking.public.contract import BookingSnapshot
from app.modules.property.public.contract import HoldResult
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

#: Payments acts as the system, not as a user. Distinguishable in audit logs
#: from a support agent confirming a booking by hand.
_SYSTEM = Actor.system()


@dataclass(slots=True)
class SqlBookingPaymentService:
    """Implements
    :class:`app.modules.booking.public.contract.BookingPaymentService`."""

    session: AsyncSession
    # SystemClock is stateless, but a shared mutable default on a dataclass is
    # a bug waiting to be introduced by the next person who gives a clock state.
    clock: Clock = field(default_factory=SystemClock)

    async def snapshot(self, booking_id: uuid.UUID) -> BookingSnapshot | None:
        booking = await SqlBookingRepository(self.session).get(booking_id)
        if booking is None:
            return None
        return BookingSnapshot(
            id=booking.id,
            reference=str(booking.reference),
            guest_id=booking.guest_id,
            guest_email=booking.guest.email,
            guest_name=booking.guest.full_name,
            guest_phone=booking.guest.phone,
            vendor_id=booking.vendor_id,
            property_name=booking.property_name,
            amount=booking.charges.total,
            status=booking.status.value,
            hold_expires_at=booking.hold.expires_at if booking.hold else None,
            # Computed here so payments never has to learn booking's status
            # vocabulary — and so adding a status does not silently make an
            # unpayable booking payable.
            is_payable=booking.status
            in (BookingStatus.PENDING_PAYMENT, BookingStatus.PENDING_APPROVAL),
            property_id=booking.property_id,
            check_out=booking.stay.check_out_date,
            # Only a completed stay. `in_stay` is deliberately excluded — a
            # review written from the lobby on the first morning is not a review
            # of the stay.
            is_reviewable=booking.status is BookingStatus.COMPLETED,
        )

    async def confirm_paid(
        self, *, booking_id: uuid.UUID, payment_id: str, paid_amount: Money
    ) -> str | None:
        """Confirm through the booking module's own use case.

        Deliberately not an UPDATE from here: confirmation issues an invoice
        number, publishes ``BookingConfirmed`` and re-checks the hold. A
        shortcut that set ``status='confirmed'`` would skip all three and leave
        a paid booking with no invoice and no confirmation email.
        """
        repo = SqlBookingRepository(self.session)
        use_case = ConfirmBookingUseCase(
            bookings=repo,
            invoice_numbers=SqlInvoiceNumberGenerator(self.session),
            inventory=_NullInventory(),
            clock=self.clock,
        )
        view = await use_case.execute(
            ConfirmBookingInput(
                booking_id=booking_id,
                payment_id=payment_id,
                paid_amount_minor=paid_amount.amount_minor,
            ),
            _SYSTEM,
        )
        await repo.flush()
        logger.info(
            "booking_confirmed_by_payment",
            booking_id=str(booking_id),
            payment_id=payment_id,
            invoice=view.invoice_number,
        )
        return view.invoice_number

    async def record_refund_result(
        self,
        *,
        booking_id: uuid.UUID,
        succeeded: bool,
        gateway_refund_id: str | None = None,
        error: str | None = None,
    ) -> None:
        repo = SqlBookingRepository(self.session)
        booking = await repo.get(booking_id)
        if booking is None or booking.refund is None:
            logger.warning("refund_result_for_unknown_booking", booking_id=str(booking_id))
            return

        now = self.clock.now()
        if succeeded:
            booking.mark_refund_completed(gateway_refund_id=gateway_refund_id or "unknown", now=now)
        else:
            booking.mark_refund_failed(error=error or "unknown error", now=now)
        await repo.flush()


class _NullInventory:
    """Confirmation does not touch inventory — the hold already holds it.

    The use case takes an ``InventoryService`` because other paths through it
    might, so this satisfies the signature without pretending to do anything.
    Every method is unreachable from the confirm path; if one is ever called,
    it fails loudly rather than silently doing nothing to real inventory.
    """

    async def hold(  # pragma: no cover
        self,
        room_type_id: uuid.UUID,
        span: DateRange,
        *,
        units: int,
        default_units: int,
    ) -> HoldResult:
        msg = "Confirmation must not take inventory — the hold already holds it"
        raise AssertionError(msg)

    async def release(  # pragma: no cover
        self, room_type_id: uuid.UUID, span: DateRange, *, units: int
    ) -> int:
        msg = "Confirmation must not release inventory"
        raise AssertionError(msg)

    async def availability(  # pragma: no cover
        self, room_type_id: uuid.UUID, span: DateRange, *, default_units: int
    ) -> Sequence[date]:
        return ()
