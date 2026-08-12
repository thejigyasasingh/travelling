"""The vendor calendar: rates and availability.

Reads densify the sparse inventory rows against the room-type defaults (see
``domain/availability.py``); writes go the other way and only persist dates
that actually deviate.

Both directions are **range operations**, because that is how vendors think —
"₹15,000 for all of December", "closed for monsoon" — and because 90 separate
requests would be 90 transactions and 90 cache invalidations for one intent.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.types.date_range import DateRange
from app.core.types.money import Money
from app.modules.property.application.dto import (
    CalendarDay,
    CalendarView,
    SetAvailabilityInput,
    SetRatesInput,
)
from app.modules.property.application.ports import CalendarRepository, PropertyRepository
from app.modules.property.domain import errors
from app.modules.property.domain.availability import (
    DayAvailability,
    assert_can_block,
    assert_can_reduce_units,
    assert_within_horizon,
)
from app.modules.property.domain.entities import Property, RoomType
from app.modules.property.domain.events import AvailabilityChanged, RatesChanged
from app.modules.property.domain.pricing import resolve_nightly_rate
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)

#: Longest span a single calendar read may cover. A year is what a calendar UI
#: shows; more than that is a bulk export, which belongs in a background job.
MAX_CALENDAR_SPAN_DAYS: Final = 400


@dataclass(slots=True)
class GetCalendarUseCase:
    properties: PropertyRepository
    calendar: CalendarRepository
    clock: Clock

    async def execute(
        self, args: tuple[uuid.UUID, uuid.UUID, date, date], actor: Actor
    ) -> CalendarView:
        """One room type's rates and availability, day by day.

        Every day is returned — including the ones with no row — because a
        calendar with gaps is unreadable. ``is_default`` tells the UI which
        ones are merely inherited.
        """
        property_id, room_type_id, from_date, to_date = args
        # `_load` performs the vendor-scope check; only the room is used here.
        _prop, room = await self._load(property_id, room_type_id, actor)
        span = _validated_span(from_date, to_date)

        window = await self.calendar.window(room.id, span, default_units=room.total_units)
        overrides = await self.calendar.rate_overrides(room.id, span)

        days: list[CalendarDay] = []
        for day in window:
            nightly = resolve_nightly_rate(day.stay_date, room.rate, overrides)
            days.append(
                CalendarDay(
                    stay_date=day.stay_date,
                    units_total=day.units_total,
                    units_booked=day.units_booked,
                    units_available=day.units_available,
                    is_blocked=day.is_blocked,
                    rate_minor=nightly.amount.amount_minor,
                    rate_source=nightly.source,
                    min_nights=day.min_nights_override or room.rate.min_nights,
                    is_default=day.is_default,
                )
            )

        return CalendarView(
            room_type_id=room.id,
            room_type_name=room.name,
            currency=room.rate.currency,
            from_date=span.start,
            to_date=span.end,
            days=days,
        )

    async def _load(
        self, property_id: uuid.UUID, room_type_id: uuid.UUID, actor: Actor
    ) -> tuple[Property, RoomType]:
        prop = await self.properties.get_for_vendor(
            property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", property_id)
        prop.assert_owned_by(actor.vendor_id)
        return prop, prop.room_type(room_type_id)


@dataclass(slots=True)
class SetRatesUseCase:
    properties: PropertyRepository
    calendar: CalendarRepository
    clock: Clock

    async def execute(self, data: SetRatesInput, actor: Actor) -> int:
        """Set or clear rate overrides across a range.

        ``rate_minor=None`` clears the override, so the date falls back to the
        weekend or base rate. That is deliberately distinct from setting the
        rate *to* the base value: a cleared date follows future base-rate
        changes, a pinned one does not.

        ``weekdays`` narrows the edit — "₹15,000 on weekends in December" in
        one call rather than eight.
        """
        prop, room = await self._load(data, actor)
        span = _validated_span(data.from_date, data.to_date)
        assert_within_horizon(span, self.clock.now().date())

        rate = Money(data.rate_minor, room.rate.currency) if data.rate_minor is not None else None
        if rate is not None and not rate.is_positive:
            msg = "A nightly rate must be positive"
            raise errors.SearchWindowError(msg)

        affected = await self.calendar.set_rates(
            room.id,
            span,
            rate=rate,
            min_nights=data.min_nights,
            weekdays=frozenset(data.weekdays) if data.weekdays else None,
            default_units=room.total_units,
        )

        # Search caches and any "from ₹X" figure are now stale.
        prop.record(
            RatesChanged(
                aggregate_id=prop.id,
                room_type_id=room.id,
                from_date=span.start.isoformat(),
                to_date=span.end.isoformat(),
                dates_affected=affected,
            )
        )
        logger.info(
            "rates_updated",
            property_id=str(prop.id),
            room_type_id=str(room.id),
            dates=affected,
            cleared=rate is None,
        )
        return affected

    async def _load(self, data: SetRatesInput, actor: Actor) -> tuple[Property, RoomType]:
        prop = await self.properties.get_for_vendor(
            data.property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", data.property_id)
        prop.assert_owned_by(actor.vendor_id)
        return prop, prop.room_type(data.room_type_id)


@dataclass(slots=True)
class SetAvailabilityUseCase:
    properties: PropertyRepository
    calendar: CalendarRepository
    clock: Clock

    async def execute(self, data: SetAvailabilityInput, actor: Actor) -> int:
        """Block, unblock, or change unit counts across a range.

        The two guards here both protect an existing guest:

        * blocking a date that already has a confirmed booking would silently
          invalidate that reservation, and the guest would find out at the door;
        * reducing unit counts below what is already booked *is* an
          overbooking.

        Both refuse with the offending date, so the vendor knows what to fix.
        """
        prop = await self.properties.get_for_vendor(
            data.property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", data.property_id)
        prop.assert_owned_by(actor.vendor_id)
        room = prop.room_type(data.room_type_id)

        span = _validated_span(data.from_date, data.to_date)
        assert_within_horizon(span, self.clock.now().date())

        window = await self.calendar.window(room.id, span, default_units=room.total_units)

        if data.is_blocked:
            assert_can_block(window)
        if data.units_total is not None:
            assert_can_reduce_units(window, data.units_total)

        days = [
            DayAvailability(
                stay_date=day.stay_date,
                units_total=(data.units_total if data.units_total is not None else day.units_total),
                units_booked=day.units_booked,
                is_blocked=(data.is_blocked if data.is_blocked is not None else day.is_blocked),
                rate_override_minor=day.rate_override_minor,
                min_nights_override=day.min_nights_override,
            )
            for day in window
        ]
        affected = await self.calendar.upsert_days(room.id, days, currency=room.rate.currency)

        prop.record(
            AvailabilityChanged(
                aggregate_id=prop.id,
                room_type_id=room.id,
                from_date=span.start.isoformat(),
                to_date=span.end.isoformat(),
                blocked=data.is_blocked,
                dates_affected=affected,
            )
        )
        logger.info(
            "availability_updated",
            property_id=str(prop.id),
            room_type_id=str(room.id),
            dates=affected,
            blocked=data.is_blocked,
        )
        return affected


@dataclass(slots=True)
class GetPublicAvailabilityUseCase:
    """What a guest sees on the detail page's date picker.

    Returns availability and price per night for every room type, but **never**
    the unit counts. "Only 1 left!" is a pressure tactic that also tells a
    competitor exactly how full a property is; a boolean is all a guest needs.
    """

    properties: PropertyRepository
    calendar: CalendarRepository
    clock: Clock

    async def execute(self, args: tuple[uuid.UUID, date, date], actor: Actor) -> CalendarView:
        property_id, from_date, to_date = args
        prop = await self.properties.get_published(property_id)
        if prop is None or not prop.status.is_visible:
            raise EntityNotFoundError("Property", property_id)

        span = _validated_span(from_date, to_date)
        if not prop.room_types:  # pragma: no cover — published implies room types
            raise EntityNotFoundError("RoomType", property_id)

        # The cheapest room type is what drives the calendar's headline price.
        room = min(prop.room_types, key=lambda rt: rt.rate.base_rate.amount_minor)
        window = await self.calendar.window(room.id, span, default_units=room.total_units)
        overrides = await self.calendar.rate_overrides(room.id, span)

        days = []
        for day in window:
            nightly = resolve_nightly_rate(day.stay_date, room.rate, overrides)
            days.append(
                CalendarDay(
                    stay_date=day.stay_date,
                    units_total=0,  # withheld — see the class docstring
                    units_booked=0,
                    units_available=1 if day.is_bookable else 0,
                    is_blocked=not day.is_bookable,
                    rate_minor=nightly.amount.amount_minor,
                    rate_source=nightly.source,
                    min_nights=day.min_nights_override or room.rate.min_nights,
                    is_default=day.is_default,
                )
            )

        return CalendarView(
            room_type_id=room.id,
            room_type_name=room.name,
            currency=room.rate.currency,
            from_date=span.start,
            to_date=span.end,
            days=days,
        )


def _validated_span(from_date: date, to_date: date) -> DateRange:
    if to_date <= from_date:
        msg = "to_date must be after from_date"
        raise errors.SearchWindowError(msg, from_date=str(from_date), to_date=str(to_date))
    if (to_date - from_date) > timedelta(days=MAX_CALENDAR_SPAN_DAYS):
        msg = f"A calendar request may span at most {MAX_CALENDAR_SPAN_DAYS} days"
        raise errors.SearchWindowError(msg, max_days=MAX_CALENDAR_SPAN_DAYS)
    return DateRange(from_date, to_date)
