"""Room types and their rate configuration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.types.date_range import DateRange
from app.core.types.money import Money
from app.modules.property.application.dto import (
    CreateRoomTypeInput,
    RoomTypeView,
    UpdateRoomTypeInput,
)
from app.modules.property.application.ports import (
    AmenityCatalog,
    CalendarRepository,
    PropertyRepository,
)
from app.modules.property.application.views import to_room_view
from app.modules.property.domain import errors
from app.modules.property.domain.availability import assert_can_reduce_units
from app.modules.property.domain.entities import RoomType
from app.modules.property.domain.pricing import PricingError, RateConfig
from app.modules.property.domain.value_objects import BedType, Occupancy
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)

#: How far ahead `assert_can_reduce_units` looks for conflicting bookings.
#: Matches the booking horizon — a reduction must not orphan a reservation
#: taken for next season.
CAPACITY_CHECK_DAYS = 550


@dataclass(slots=True)
class AddRoomTypeUseCase:
    properties: PropertyRepository
    amenities: AmenityCatalog

    async def execute(self, data: CreateRoomTypeInput, actor: Actor) -> RoomTypeView:
        prop = await self.properties.get_for_vendor(
            data.property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", data.property_id)
        prop.assert_owned_by(actor.vendor_id)

        if data.amenity_codes:
            await self.amenities.validate(frozenset(data.amenity_codes))

        room = RoomType(
            name=data.name,
            rate=_build_rate(data, prop.currency),
            max_occupancy=Occupancy(adults=data.max_adults, children=data.max_children),
            total_units=data.total_units,
            bed_type=BedType(data.bed_type),
            description=data.description,
            size_sqft=data.size_sqft,
            amenity_codes=frozenset(data.amenity_codes),
        )
        # Enforces the whole-unit rule (a villa is one bookable unit) and the
        # duplicate-name rule.
        prop.add_room_type(room)

        logger.info(
            "room_type_added",
            property_id=str(prop.id),
            room_type_id=str(room.id),
            units=room.total_units,
        )
        return to_room_view(room)


@dataclass(slots=True)
class UpdateRoomTypeUseCase:
    properties: PropertyRepository
    calendar: CalendarRepository
    amenities: AmenityCatalog
    clock: Clock

    async def execute(self, data: UpdateRoomTypeInput, actor: Actor) -> RoomTypeView:
        prop = await self.properties.get_for_vendor(
            data.property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", data.property_id)
        prop.assert_owned_by(actor.vendor_id)
        prop.assert_editable()

        room = prop.room_type(data.room_type_id)

        if data.amenity_codes is not None:
            await self.amenities.validate(frozenset(data.amenity_codes))

        if data.total_units is not None and data.total_units != room.total_units:
            await self._assert_capacity_reduction_is_safe(room, data.total_units)
            room.total_units = data.total_units

        if data.name is not None and data.name.strip():
            new_name = data.name.strip()
            if any(
                rt.id != room.id and rt.name.casefold() == new_name.casefold()
                for rt in prop.room_types
            ):
                raise errors.DuplicateRoomTypeError(new_name)
            room.name = new_name

        if data.description is not None:
            room.description = data.description
        if data.size_sqft is not None:
            room.size_sqft = data.size_sqft
        if data.amenity_codes is not None:
            room.amenity_codes = frozenset(data.amenity_codes)
        if data.max_adults is not None or data.max_children is not None:
            room.max_occupancy = Occupancy(
                adults=data.max_adults or room.max_occupancy.adults,
                children=(
                    data.max_children
                    if data.max_children is not None
                    else room.max_occupancy.children
                ),
            )

        room.rate = _merge_rate(room.rate, data)

        logger.info("room_type_updated", property_id=str(prop.id), room_type_id=str(room.id))
        return to_room_view(room)

    async def _assert_capacity_reduction_is_safe(self, room: RoomType, new_total: int) -> None:
        """A hotel dropping from five units to two when three are booked on the
        14th is describing an overbooking.

        Checked against the whole booking horizon, not just the next month —
        the conflict is usually in peak season, which is months out.
        """
        if new_total >= room.total_units:
            return  # increasing capacity is always safe
        today = self.clock.now().date()
        span = DateRange(today, today + timedelta(days=CAPACITY_CHECK_DAYS))
        window = await self.calendar.window(room.id, span, default_units=room.total_units)
        assert_can_reduce_units(window, new_total)


@dataclass(slots=True)
class RemoveRoomTypeUseCase:
    properties: PropertyRepository

    async def execute(self, args: tuple[uuid.UUID, uuid.UUID], actor: Actor) -> None:
        property_id, room_type_id = args
        prop = await self.properties.get_for_vendor(
            property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", property_id)
        prop.assert_owned_by(actor.vendor_id)

        # Refuses to leave a published listing with no rooms — which would
        # render as a live page nobody can book.
        prop.remove_room_type(room_type_id)
        logger.info("room_type_removed", property_id=str(prop.id), room_type_id=str(room_type_id))


# ══════════════════════════════════════════════════════════════════════════
# Rate construction
# ══════════════════════════════════════════════════════════════════════════


def _money(minor: int | None, currency: str) -> Money | None:
    return Money(minor, currency) if minor is not None else None


def _build_rate(data: CreateRoomTypeInput, currency: str) -> RateConfig:
    try:
        tax_rate = Decimal(data.tax_rate)
    except (InvalidOperation, ValueError) as exc:
        msg = f"tax_rate {data.tax_rate!r} is not a valid decimal"
        raise PricingError(msg) from exc

    return RateConfig(
        base_rate=Money(data.base_rate_minor, currency),
        weekend_rate=_money(data.weekend_rate_minor, currency),
        included_guests=data.included_guests,
        extra_guest_rate=_money(data.extra_guest_rate_minor, currency),
        min_nights=data.min_nights,
        max_nights=data.max_nights,
        tax_rate=tax_rate,
        cleaning_fee=_money(data.cleaning_fee_minor, currency),
    )


def _merge_rate(current: RateConfig, data: UpdateRoomTypeInput) -> RateConfig:
    """Rebuild the frozen config from a partial update.

    ``RateConfig`` is immutable, so a partial edit means constructing a new one
    — which re-runs every validator. A vendor cannot end up with
    ``max_nights < min_nights`` by editing only one of them.
    """
    currency = current.currency
    return RateConfig(
        base_rate=(
            Money(data.base_rate_minor, currency)
            if data.base_rate_minor is not None
            else current.base_rate
        ),
        weekend_rate=(
            _money(data.weekend_rate_minor, currency)
            if data.weekend_rate_minor is not None
            else current.weekend_rate
        ),
        included_guests=(
            data.included_guests if data.included_guests is not None else current.included_guests
        ),
        extra_guest_rate=(
            _money(data.extra_guest_rate_minor, currency)
            if data.extra_guest_rate_minor is not None
            else current.extra_guest_rate
        ),
        min_nights=data.min_nights if data.min_nights is not None else current.min_nights,
        max_nights=data.max_nights if data.max_nights is not None else current.max_nights,
        tax_rate=current.tax_rate,
        cleaning_fee=(
            _money(data.cleaning_fee_minor, currency)
            if data.cleaning_fee_minor is not None
            else current.cleaning_fee
        ),
    )
