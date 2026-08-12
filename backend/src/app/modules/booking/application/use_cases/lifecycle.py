"""Confirm, approve, reject, expire, check in, complete.

Every one of these mutates a booking *and* may move inventory, and every one
runs in a single transaction so the two can never disagree.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.types.date_range import DateRange
from app.core.types.money import Money
from app.modules.booking.application.dto import BookingView, ConfirmBookingInput
from app.modules.booking.application.ports import (
    BookingRepository,
    CommissionCalculator,
    InvoiceNumberGenerator,
)
from app.modules.booking.application.views import to_booking_view
from app.modules.booking.domain import errors
from app.modules.booking.domain.entities import Booking
from app.modules.booking.domain.value_objects import BookingStatus
from app.modules.property.public import InventoryService
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)


@dataclass(slots=True)
class ConfirmBookingUseCase:
    """Payment succeeded — commit the booking.

    Called from the payment webhook, not from the browser. A client-reported
    "I paid" is a claim; the gateway's signed callback is evidence.
    """

    bookings: BookingRepository
    invoice_numbers: InvoiceNumberGenerator
    inventory: InventoryService
    clock: Clock

    async def execute(self, data: ConfirmBookingInput, actor: Actor) -> BookingView:
        now = self.clock.now()
        booking = await self.bookings.get(data.booking_id)
        if booking is None:
            raise EntityNotFoundError("Booking", data.booking_id)

        # Idempotent: gateways retry webhooks, and a retry must not issue a
        # second invoice number or publish a second confirmation email.
        if booking.status is BookingStatus.CONFIRMED:
            logger.info("booking_confirm_replayed", booking_id=str(booking.id))
            return to_booking_view(booking, now=now, include_address=True)

        # The amount the gateway actually captured, cross-checked. A mismatch
        # is either a tampered client or a bug in our own pricing; either way
        # it must stop here rather than be reconciled by hand next month.
        if data.paid_amount_minor is not None:
            expected = booking.total.amount_minor
            if data.paid_amount_minor != expected:
                logger.error(
                    "payment_amount_mismatch",
                    booking_id=str(booking.id),
                    expected_minor=expected,
                    received_minor=data.paid_amount_minor,
                )
                raise errors.PriceChangedError(
                    data.paid_amount_minor, expected, booking.total.currency
                )

        if booking.is_hold_expired(now):
            # A guest completing 3-D Secure at minute 16. The inventory is
            # already released and may have been resold, so the booking is not
            # resurrected — the payment module refunds instead.
            logger.warning(
                "booking_confirm_after_expiry",
                booking_id=str(booking.id),
                reference=str(booking.reference),
            )
            raise errors.HoldExpiredError

        # The invoice number is taken *inside* this transaction. If the
        # confirmation rolls back, the number is not consumed — which is what
        # keeps the sequence gapless.
        number = await self.invoice_numbers.next_number(issued_on=now.date())

        booking.confirm(now=now, payment_id=data.payment_id, invoice_number=number)

        logger.info(
            "booking_confirmed",
            booking_id=str(booking.id),
            reference=str(booking.reference),
            invoice_number=number,
            total_minor=booking.total.amount_minor,
        )
        return to_booking_view(booking, now=now, include_address=True)


@dataclass(slots=True)
class ExpireHoldsUseCase:
    """Release inventory from lapsed holds. Runs every minute on Beat.

    The most operationally important background job in the system: if it stops,
    inventory silently leaks and properties go dark on their busiest dates with
    no error anywhere.
    """

    bookings: BookingRepository
    inventory: InventoryService
    clock: Clock

    async def execute(self, limit: int, actor: Actor) -> int:
        now = self.clock.now()
        # Claimed with FOR UPDATE SKIP LOCKED, so several workers can run
        # concurrently without double-releasing the same booking.
        expired = await self.bookings.find_expired_holds(now=now, limit=limit)

        released = 0
        for booking in expired:
            span = DateRange(booking.stay.check_in_date, booking.stay.check_out_date)
            await self.inventory.release(booking.room_type_id, span, units=booking.rooms)
            booking.expire(now=now)
            released += 1
            logger.info(
                "booking_hold_expired",
                booking_id=str(booking.id),
                reference=str(booking.reference),
                nights=span.night_count,
            )

        if released:
            logger.info("holds_expired_batch", count=released)
        return released


@dataclass(slots=True)
class ApproveBookingUseCase:
    """Vendor accepts a request-to-book. The guest is then asked to pay."""

    bookings: BookingRepository
    clock: Clock

    async def execute(self, booking_id: uuid.UUID, actor: Actor) -> BookingView:
        now = self.clock.now()
        booking = await self._vendor_booking(booking_id, actor)
        booking.approve(now=now)
        logger.info("booking_approved", booking_id=str(booking.id))
        return to_booking_view(booking, now=now, include_address=False)

    async def _vendor_booking(self, booking_id: uuid.UUID, actor: Actor) -> Booking:
        booking = await self.bookings.get(booking_id)
        if booking is None:
            raise EntityNotFoundError("Booking", booking_id)
        booking.assert_visible_to(user_id=None, vendor_id=actor.vendor_id)
        return booking


@dataclass(slots=True)
class RejectBookingUseCase:
    """Vendor declines. Inventory is released immediately — holding dates for a
    booking that will never happen is lost revenue for the vendor and a
    property that looks sold out to everyone else."""

    bookings: BookingRepository
    inventory: InventoryService
    clock: Clock

    async def execute(self, args: tuple[uuid.UUID, str], actor: Actor) -> BookingView:
        booking_id, reason = args
        now = self.clock.now()

        booking = await self.bookings.get(booking_id)
        if booking is None:
            raise EntityNotFoundError("Booking", booking_id)
        booking.assert_visible_to(user_id=None, vendor_id=actor.vendor_id)

        span = DateRange(booking.stay.check_in_date, booking.stay.check_out_date)
        await self.inventory.release(booking.room_type_id, span, units=booking.rooms)
        booking.reject(now=now, reason=reason)

        logger.info("booking_rejected", booking_id=str(booking.id), reason=reason)
        return to_booking_view(booking, now=now, include_address=False)


@dataclass(slots=True)
class StartStaysUseCase:
    """Move today's arrivals to `in_stay`. Runs daily.

    The status matters for cancellation: once a stay has started, a guest
    leaving early negotiates with the vendor rather than getting an automatic
    refund.
    """

    bookings: BookingRepository
    clock: Clock

    async def execute(self, limit: int, actor: Actor) -> int:
        now = self.clock.now()
        due = await self.bookings.find_due_for_check_in(today=now.date(), limit=limit)
        for booking in due:
            booking.check_in(now=now)
        if due:
            logger.info("stays_started", count=len(due))
        return len(due)


@dataclass(slots=True)
class CompleteStaysUseCase:
    """Close out yesterday's departures and release vendor payouts.

    Payout is deliberately held until after checkout. Paying on confirmation
    would mean clawing money back on every cancellation, and by then it is
    usually spent.
    """

    bookings: BookingRepository
    inventory: InventoryService
    commission: CommissionCalculator
    clock: Clock

    async def execute(self, limit: int, actor: Actor) -> int:
        now = self.clock.now()
        due = await self.bookings.find_due_for_completion(today=now.date(), limit=limit)

        for booking in due:
            cut = await self.commission.commission_for(
                vendor_id=booking.vendor_id,
                property_id=booking.property_id,
                amount=booking.charges.accommodation,
            )
            booking.complete(now=now, platform_commission=cut)
            logger.info(
                "booking_completed",
                booking_id=str(booking.id),
                commission_minor=cut.amount_minor,
            )

        if due:
            logger.info("stays_completed", count=len(due))
        return len(due)


@dataclass(slots=True)
class FlatCommission:
    """Default commission policy: a flat percentage of accommodation.

    Tax is excluded from the base — commission on tax would mean taking a cut
    of money that belongs to the government. So is the cleaning fee, which
    covers a real cost the vendor incurs.
    """

    percent: str = "0.15"

    async def commission_for(
        self, *, vendor_id: uuid.UUID, property_id: uuid.UUID, amount: Money
    ) -> Money:
        from decimal import Decimal

        return amount.percentage(Decimal(self.percent))


def _now_or(clock: Clock, when: datetime | None) -> datetime:  # pragma: no cover
    return when or clock.now()
