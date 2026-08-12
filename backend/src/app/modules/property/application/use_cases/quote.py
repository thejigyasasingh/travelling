"""Price a specific stay.

The number this returns is the one the guest sees on the booking screen, and
the booking module re-computes it server-side before charging. That
re-computation is not redundancy for its own sake: a quote is a *snapshot*, and
between seeing it and paying, a vendor may change rates or another guest may
take the last room. The booking either matches this price or tells the guest it
changed — it never silently charges a different amount.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.types.date_range import DateRange
from app.modules.property.application.ports import CalendarRepository, PropertyRepository
from app.modules.property.domain import errors
from app.modules.property.domain.entities import Property, RoomType
from app.modules.property.domain.pricing import Quote, quote_stay, validate_stay_length
from app.modules.property.domain.value_objects import Occupancy
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class QuoteResult:
    room_type_id: uuid.UUID
    quote: Quote
    is_available: bool
    unavailable_dates: list[date]


@dataclass(slots=True)
class QuoteStayUseCase:
    properties: PropertyRepository
    calendar: CalendarRepository
    clock: Clock

    async def execute(
        self, args: tuple[uuid.UUID, uuid.UUID | None, DateRange, Occupancy, int], actor: Actor
    ) -> QuoteResult:
        """Quote one room type, or the cheapest one that fits.

        Availability is reported alongside the price rather than replacing it.
        A sold-out property that answers "no" and nothing else gives the guest
        nowhere to go; returning the price *and* the blocking dates lets the UI
        offer adjacent nights, which is where a large share of bookings that
        would otherwise be lost actually come from.
        """
        property_id, room_type_id, stay, occupancy, rooms = args

        prop = await self.properties.get_published(property_id)
        if prop is None:
            raise EntityNotFoundError("Property", property_id)

        if stay.start < self.clock.now().date():
            msg = "Check-in cannot be in the past"
            raise errors.SearchWindowError(msg)

        room = (
            prop.room_type(room_type_id)
            if room_type_id is not None
            else self._cheapest_fitting(prop, occupancy)
        )

        # Raises with the vendor's actual minimum, so the UI can say "this
        # property requires 3 nights" instead of a bare rejection.
        validate_stay_length(stay, room.rate)

        if not room.accommodates(occupancy):
            msg = f"{room.name} accommodates at most {room.max_occupancy.billable_guests} guests"
            raise errors.SearchWindowError(msg, max_guests=room.max_occupancy.billable_guests)

        overrides = await self.calendar.rate_overrides(room.id, stay)
        window = await self.calendar.window(room.id, stay, default_units=room.total_units)

        quote = quote_stay(
            stay,
            room.rate,
            billable_guests=occupancy.billable_guests,
            overrides=overrides,
            units=rooms,
        )

        logger.info(
            "stay_quoted",
            property_id=str(prop.id),
            room_type_id=str(room.id),
            nights=stay.night_count,
            total_minor=quote.total.amount_minor,
            available=window.is_available(rooms),
        )
        return QuoteResult(
            room_type_id=room.id,
            quote=quote,
            is_available=window.is_available(rooms),
            unavailable_dates=list(window.unavailable_dates(rooms)),
        )

    @staticmethod
    def _cheapest_fitting(prop: Property, occupancy: Occupancy) -> RoomType:
        """Default to the cheapest room that actually fits the party.

        Not simply the cheapest: offering a ₹4,000 room that sleeps two to a
        family of four is a quote that cannot become a booking.
        """
        candidates = [rt for rt in prop.room_types if rt.accommodates(occupancy)]
        if not candidates:
            msg = f"No room at this property accommodates {occupancy.billable_guests} guests"
            raise errors.SearchWindowError(msg, guests=occupancy.billable_guests)
        return min(candidates, key=lambda rt: rt.rate.base_rate.amount_minor)
