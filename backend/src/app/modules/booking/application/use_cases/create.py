"""Creating a booking — taking the hold.

The order of operations here is the design, and it is not the obvious one:

1. Load the property snapshot and validate the stay *cheaply* — dates, party
   size, minimum nights. Failing fast avoids touching inventory for a request
   that was never going to succeed.
2. **Re-price server-side** and compare against what the guest was quoted.
3. **Take the inventory hold.** This is the atomic step and the only one that
   can fail on contention.
4. Create the booking row in the *same transaction* as the hold.

Steps 3 and 4 being one transaction is what makes "a booking always has the
inventory it claims" true. If they were separate, a crash between them would
leave either a booking with no room or a room held by nobody — and the second
is invisible until a vendor complains that their calendar is wrong.

Note what is deliberately absent: an availability *check* before the hold. That
would be a check-then-act race. Availability is only ever read to *explain* a
refusal after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Final
from zoneinfo import ZoneInfo

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.types.date_range import DateRange
from app.core.types.money import Money
from app.modules.booking.application.dto import BookingView, CreateBookingInput
from app.modules.booking.application.ports import BookingRepository
from app.modules.booking.application.views import to_booking_view
from app.modules.booking.domain import errors
from app.modules.booking.domain.entities import PRICE_TOLERANCE_MINOR, Booking
from app.modules.booking.domain.refund_policy import ChargeBreakdown, PolicyName
from app.modules.booking.domain.value_objects import GuestDetails, StayWindow
from app.modules.property.domain.pricing import (
    NightlyRate,
    PricingError,
    validate_stay_length,
)
from app.modules.property.domain.value_objects import Occupancy
from app.modules.property.public import (
    InventoryService,
    PropertyCatalog,
    PropertySnapshot,
    RoomSnapshot,
    price_stay,
)
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

#: A stay cannot start today after check-in time has passed, and same-day
#: bookings need the vendor to actually be able to receive the guest.
MIN_LEAD_HOURS: Final = 0
MAX_ROOMS_PER_BOOKING: Final = 8


@dataclass(slots=True)
class CreateBookingUseCase:
    bookings: BookingRepository
    catalog: PropertyCatalog
    inventory: InventoryService
    clock: Clock

    async def execute(self, data: CreateBookingInput, actor: Actor) -> BookingView:
        if actor.user_id is None:  # pragma: no cover — route requires auth
            raise errors.BookingAccessDeniedError

        now = self.clock.now()
        stay_range = self._validated_range(data, now)

        snapshot = await self.catalog.snapshot(data.property_id)
        if snapshot is None or not snapshot.is_bookable:
            raise errors.PropertyNotBookableError("not_published")

        room = snapshot.room(data.room_type_id)
        if room is None:
            raise errors.PropertyNotBookableError("unknown_room_type")

        occupancy = Occupancy(adults=data.adults, children=data.children, infants=data.infants)
        self._validate_capacity(room, occupancy, data.rooms)

        try:
            validate_stay_length(stay_range, room.rate)
        except PricingError as exc:
            raise errors.InvalidStayError(str(exc), nights=stay_range.night_count) from exc

        charges, nights = await self._price(room, stay_range, occupancy, data.rooms)

        # The guest agreed to a number. If it moved, they see the new one and
        # decide again — silently charging a different amount is a chargeback.
        self._assert_price_unchanged(data.quoted_total_minor, charges.total)

        # THE atomic step. No preceding availability check by design.
        hold = await self.inventory.hold(
            room.id,
            stay_range,
            units=data.rooms,
            default_units=room.total_units,
        )
        if not hold.granted:
            logger.info(
                "booking_rejected_no_inventory",
                property_id=str(snapshot.id),
                room_type_id=str(room.id),
                nights=stay_range.night_count,
            )
            raise errors.DatesUnavailableError(list(hold.unavailable_dates))

        booking = Booking.hold_inventory(
            guest_id=actor.user_id,
            guest=GuestDetails(
                full_name=data.guest_name.strip(),
                email=data.guest_email.strip().lower(),
                phone=data.guest_phone.strip(),
                special_requests=data.special_requests,
            ),
            property_id=snapshot.id,
            property_name=snapshot.name,
            vendor_id=snapshot.vendor_id,
            room_type_id=room.id,
            room_type_name=room.name,
            stay=self._stay_window(snapshot, stay_range),
            charges=charges,
            cancellation_policy=PolicyName(snapshot.cancellation_policy),
            now=now,
            adults=data.adults,
            children=data.children,
            infants=data.infants,
            rooms=data.rooms,
            # A vendor who reviews each request gets a longer window; the guest
            # is not asked to pay until the vendor accepts.
            requires_approval=not snapshot.instant_booking,
            nightly_rates=[
                {
                    "date": night.stay_date.isoformat(),
                    "amount_minor": night.amount.amount_minor,
                    "source": night.source,
                }
                for night in nights
            ],
            source=data.source,
        )
        # Written in the SAME transaction as the hold above.
        await self.bookings.add(booking)

        logger.info(
            "booking_held",
            booking_id=str(booking.id),
            reference=str(booking.reference),
            property_id=str(snapshot.id),
            nights=stay_range.night_count,
            total_minor=charges.total.amount_minor,
            requires_approval=not snapshot.instant_booking,
        )
        return to_booking_view(booking, now=now, include_address=False)

    # ── validation ────────────────────────────────────────────────────────

    def _validated_range(self, data: CreateBookingInput, now: datetime) -> DateRange:
        if data.check_out <= data.check_in:
            raise errors.InvalidStayError("Check-out must be after check-in")
        if data.check_in < now.date():
            raise errors.InvalidStayError("Check-in cannot be in the past")
        if not 1 <= data.rooms <= MAX_ROOMS_PER_BOOKING:
            raise errors.InvalidStayError(
                f"A booking may cover between 1 and {MAX_ROOMS_PER_BOOKING} rooms",
                rooms=data.rooms,
            )
        return DateRange(data.check_in, data.check_out)

    @staticmethod
    def _validate_capacity(room: RoomSnapshot, occupancy: Occupancy, rooms: int) -> None:
        """Capacity is per room, multiplied by the number booked.

        Not the property's total: a guest booking two rooms gets two rooms'
        worth of capacity, but a party of six cannot be squeezed into one room
        that sleeps two just because the property has other rooms.
        """
        capacity = room.max_billable_guests * rooms
        if occupancy.billable_guests > capacity:
            raise errors.OccupancyExceededError(occupancy.billable_guests, capacity)

    async def _price(
        self,
        room: RoomSnapshot,
        stay: DateRange,
        occupancy: Occupancy,
        rooms: int,
    ) -> tuple[ChargeBreakdown, list[NightlyRate]]:
        """Re-price server-side, from the property module's own engine.

        Using the same code the guest was quoted with is what makes the
        comparison in :meth:`_assert_price_unchanged` meaningful — a
        reimplementation here would drift and start rejecting valid bookings.
        """
        overrides = await self.catalog.rate_overrides(room.id, stay)
        quote = price_stay(
            stay,
            room.rate,
            billable_guests=occupancy.billable_guests,
            overrides=overrides,
            units=rooms,
        )
        charges = ChargeBreakdown(
            accommodation=quote.accommodation,
            extra_guest=quote.extra_guest_total,
            cleaning_fee=quote.cleaning_fee,
            tax=quote.tax,
            # Commission is taken from the vendor's payout, not added to the
            # guest's bill — the guest pays the advertised price.
            platform_fee=Money.zero(quote.currency),
        )
        # The per-night breakdown is returned rather than stashed: it belongs
        # to this call, and a field on the use case would leak between calls.
        return charges, list(quote.nights)

    @staticmethod
    def _assert_price_unchanged(quoted_minor: int | None, current: Money) -> None:
        if quoted_minor is None:
            return  # a client that did not quote accepts the server price
        if abs(current.amount_minor - quoted_minor) <= PRICE_TOLERANCE_MINOR:
            return  # rounding noise from a rate edit, not a real change
        raise errors.PriceChangedError(quoted_minor, current.amount_minor, current.currency)

    @staticmethod
    def _stay_window(snapshot: PropertySnapshot, stay: DateRange) -> StayWindow:
        """Copy the property's check-in/out times onto the booking.

        A vendor later moving check-in from 14:00 to 15:00 must not shift the
        refund deadline of an existing booking, so the times are frozen here.
        """
        return StayWindow(
            check_in_date=stay.start,
            check_out_date=stay.end,
            check_in_time=_parse_time(snapshot.check_in_from, default=time(14, 0)),
            check_out_time=_parse_time(snapshot.check_out_by, default=time(11, 0)),
        )


def _parse_time(value: str, *, default: time) -> time:
    try:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))
    except (ValueError, AttributeError):  # pragma: no cover — schema-validated upstream
        return default


def local_now(clock: Clock, timezone: str = "Asia/Kolkata") -> datetime:
    """Wall-clock time at the property.

    Refund thresholds are "24 hours before check-in", and check-in is 14:00 *at
    the property*. Computing that in UTC is wrong by hours in exactly the
    direction that generates complaints.
    """
    return clock.now().astimezone(ZoneInfo(timezone)).replace(tzinfo=None)
