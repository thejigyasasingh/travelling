"""Cancellation and the refund workflow.

Cancelling does four things, and they must all succeed or all fail:

1. compute the refund from the charges **recorded on the booking**;
2. release the inventory;
3. move the booking to ``cancelled``;
4. record a pending refund and publish ``RefundRequested``.

The actual money movement is **not** step 5. Calling the payment gateway inside
this transaction would hold a database transaction open across a network round
trip to a third party — and if the gateway succeeded but the commit then
failed, we would have refunded a booking that is still confirmed. Instead the
refund request goes through the outbox, and a worker calls the gateway with an
idempotency key derived from the booking id.

That means a brief window where the booking is cancelled and the money has not
moved. That is the correct trade: the guest sees the cancellation immediately
and the refund follows within seconds, and neither state is ever lost.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.types.date_range import DateRange
from app.modules.booking.application.dto import BookingView, CancelBookingInput
from app.modules.booking.application.ports import BookingRepository
from app.modules.booking.application.views import to_booking_view
from app.modules.booking.domain.entities import Booking
from app.modules.booking.domain.refund_policy import describe_policy
from app.modules.booking.domain.value_objects import CancelledBy
from app.modules.property.public import InventoryService
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)

DEFAULT_TZ = "Asia/Kolkata"


@dataclass(slots=True)
class CancelBookingUseCase:
    bookings: BookingRepository
    inventory: InventoryService
    clock: Clock

    async def execute(self, data: CancelBookingInput, actor: Actor) -> BookingView:
        now = self.clock.now()
        booking = await self.bookings.get(data.booking_id)
        if booking is None:
            raise EntityNotFoundError("Booking", data.booking_id)

        cancelled_by = self._who(booking, actor)
        booking.assert_visible_to(
            user_id=actor.user_id,
            vendor_id=actor.vendor_id,
            is_staff=cancelled_by is CancelledBy.ADMIN,
        )

        # Wall-clock time at the property. Refund thresholds are "24 hours
        # before check-in", and check-in is 14:00 *there* — computing that in
        # UTC is wrong by hours, in the direction that produces complaints.
        now_local = now.astimezone(ZoneInfo(booking.stay.timezone)).replace(tzinfo=None)

        breakdown = booking.cancel(
            now_local=now_local,
            now=now,
            cancelled_by=cancelled_by,
            reason=(data.reason or "").strip() or None,
        )

        # Released only for statuses that were actually holding it. Releasing
        # for a status that was not would drive units_booked toward zero and
        # create phantom rooms.
        span = DateRange(booking.stay.check_in_date, booking.stay.check_out_date)
        await self.inventory.release(booking.room_type_id, span, units=booking.rooms)

        logger.info(
            "booking_cancelled",
            booking_id=str(booking.id),
            reference=str(booking.reference),
            cancelled_by=cancelled_by.value,
            refund_minor=breakdown.total.amount_minor,
            hours_before=round(breakdown.hours_before_check_in, 1),
        )
        return to_booking_view(booking, now=now, include_address=False)

    @staticmethod
    def _who(booking: Booking, actor: Actor) -> CancelledBy:
        """Who is cancelling changes the refund entirely.

        A vendor cancelling on a guest refunds in full regardless of policy —
        the guest is about to have their trip disrupted and must rebook at
        today's prices. Getting this attribution wrong is the difference
        between a full refund and none.
        """
        if actor.has_role("admin", "superadmin", "support"):
            return CancelledBy.ADMIN
        if actor.vendor_id is not None and actor.vendor_id == booking.vendor_id:
            return CancelledBy.VENDOR
        return CancelledBy.GUEST


@dataclass(slots=True)
class PreviewRefundUseCase:
    """What cancelling right now would return. Read-only.

    Shown *before* the confirm button. A guest who cancels and only then learns
    the amount opens a support ticket; one who sees it first mostly does not.
    """

    bookings: BookingRepository
    clock: Clock

    async def execute(self, booking_id: uuid.UUID, actor: Actor) -> dict[str, object]:
        booking = await self.bookings.get(booking_id)
        if booking is None:
            raise EntityNotFoundError("Booking", booking_id)
        booking.assert_visible_to(
            user_id=actor.user_id,
            vendor_id=actor.vendor_id,
            is_staff=actor.has_role("admin", "superadmin", "support"),
        )

        now_local = (
            self.clock.now().astimezone(ZoneInfo(booking.stay.timezone)).replace(tzinfo=None)
        )
        breakdown = booking.preview_refund(now_local)

        return {
            **breakdown.to_payload(),
            "cancellable": booking.status.is_cancellable_by_guest,
            "policy_tiers": describe_policy(booking.cancellation_policy, booking.charges.currency),
        }
