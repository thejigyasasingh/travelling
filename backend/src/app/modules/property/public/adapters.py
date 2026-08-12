"""Implementations of the published contract.

:class:`SqlInventoryService.hold` is the single most correctness-critical
function in this codebase. Read its docstring before changing anything here.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import CursorResult, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.types.date_range import DateRange
from app.core.types.money import Money
from app.modules.property.domain.pricing import RateConfig
from app.modules.property.infrastructure.models import (
    PropertyModel,
    RoomInventoryModel,
    RoomTypeModel,
)
from app.modules.property.public.contract import (
    HoldResult,
    PropertyCard,
    PropertySnapshot,
    RoomSnapshot,
)

logger = get_logger(__name__)

#: DateRange is half-open; generate_series is inclusive at both ends.
_ONE_DAY = timedelta(days=1)


def _money(minor: int | None, currency: str) -> Money | None:
    return Money(minor, currency) if minor is not None else None


@dataclass(slots=True)
class SqlPropertyCatalog:
    session: AsyncSession

    async def cards(self, property_ids: Sequence[uuid.UUID]) -> Mapping[uuid.UUID, PropertyCard]:
        """One query, whatever the list length.

        The cover image is chosen by `is_cover` first and `position` second, in
        a lateral join rather than a second round trip — a listing whose cover
        flag was never set still gets its first photograph rather than a grey
        box.

        `min_rate_minor` is the denormalised cheapest-room rate the property
        module already maintains for search. Reading it here means a wishlist
        and a search result quote the same number, which they would not if this
        recomputed it.
        """
        if not property_ids:
            return {}

        rows = (
            await self.session.execute(
                text("""
                SELECT p.id, p.slug, p.name, p.city, p.country_code, p.currency,
                       img.storage_key, p.min_rate_minor,
                       p.review_average, p.review_count,
                       (p.status = 'published' AND p.deleted_at IS NULL) AS is_live
                  FROM properties p
                  LEFT JOIN LATERAL (
                      SELECT i.storage_key
                        FROM property_images i
                       WHERE i.property_id = p.id
                       ORDER BY i.is_cover DESC, i.position
                       LIMIT 1
                  ) img ON true
                 WHERE p.id = ANY(:ids)
                """),
                {"ids": list(property_ids)},
            )
        ).all()

        return {
            row[0]: PropertyCard(
                id=row[0],
                slug=row[1],
                name=row[2],
                city=row[3],
                country_code=row[4],
                currency=row[5],
                cover_image_url=self._media_url(row[6]),
                from_price_minor=row[7],
                review_average=float(row[8] or 0),
                review_count=int(row[9] or 0),
                is_live=bool(row[10]),
            )
            for row in rows
        }

    @staticmethod
    def _media_url(storage_key: str | None) -> str | None:
        """A public URL for a stored object.

        Built from the CDN base rather than presigned: a wishlist renders
        twenty images, and twenty presigned URLs is twenty signatures with an
        expiry that outlives nothing useful. Property photographs are public —
        they are on the listing page — so they are served as public objects.
        """
        if not storage_key:
            return None
        from app.core.config import get_settings

        base = get_settings().storage.public_base_url
        return f"{base.rstrip('/')}/{storage_key.lstrip('/')}" if base else None

    async def snapshot(self, property_id: uuid.UUID) -> PropertySnapshot | None:
        row = (
            await self.session.execute(
                select(PropertyModel).where(
                    PropertyModel.id == property_id,
                    PropertyModel.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None

        rooms = tuple(
            RoomSnapshot(
                id=rt.id,
                property_id=row.id,
                name=rt.name,
                total_units=rt.total_units,
                max_adults=rt.max_adults,
                max_children=rt.max_children,
                rate=RateConfig(
                    base_rate=Money(rt.base_rate_minor, row.currency),
                    weekend_rate=_money(rt.weekend_rate_minor, row.currency),
                    included_guests=rt.included_guests,
                    extra_guest_rate=_money(rt.extra_guest_rate_minor, row.currency),
                    min_nights=rt.min_nights,
                    max_nights=rt.max_nights,
                    tax_rate=Decimal(str(rt.tax_rate)),
                    cleaning_fee=_money(rt.cleaning_fee_minor, row.currency),
                ),
            )
            for rt in row.room_types
            if rt.deleted_at is None
        )

        return PropertySnapshot(
            id=row.id,
            vendor_id=row.vendor_id,
            name=row.name,
            slug=row.slug,
            property_type=row.property_type,
            city=row.city,
            country_code=row.country_code,
            currency=row.currency,
            cancellation_policy=row.cancellation_policy,
            check_in_from=row.check_in_from,
            check_out_by=row.check_out_by,
            instant_booking=row.instant_booking,
            # Computed here rather than exposing `status`, so booking never has
            # to know the property module's lifecycle vocabulary.
            is_bookable=row.status == "published" and bool(rooms),
            rooms=rooms,
            full_address=", ".join(
                p for p in (row.line1, row.line2, row.city, row.state, row.postal_code) if p
            ),
        )

    async def rate_overrides(
        self, room_type_id: uuid.UUID, span: DateRange
    ) -> Mapping[date, Money]:
        rows = (
            await self.session.execute(
                select(RoomInventoryModel.stay_date, RoomInventoryModel.rate_override_minor).where(
                    RoomInventoryModel.room_type_id == room_type_id,
                    RoomInventoryModel.stay_date >= span.start,
                    RoomInventoryModel.stay_date < span.end,
                    RoomInventoryModel.rate_override_minor.isnot(None),
                )
            )
        ).all()
        currency = (
            await self.session.execute(
                select(PropertyModel.currency)
                .join(RoomTypeModel, RoomTypeModel.property_id == PropertyModel.id)
                .where(RoomTypeModel.id == room_type_id)
            )
        ).scalar() or "INR"
        return {row[0]: Money(row[1], currency) for row in rows}


# ══════════════════════════════════════════════════════════════════════════
# Inventory
# ══════════════════════════════════════════════════════════════════════════

#: Claim `units` on every night of a stay, in one statement.
#:
#: `generate_series` materialises the nights inside Postgres and `ORDER BY` is
#: what prevents deadlocks — see the docstring on `hold`.
#:
#: The INSERT branch handles nights with no row yet (inventory is sparse, so
#: "no row" means "fully available at the room-type default"). The ON CONFLICT
#: branch increments an existing row. Either way the CHECK constraint
#: `units_booked <= units_total` is what actually decides whether the claim is
#: legal.
_HOLD_SQL = """
INSERT INTO room_inventory
    (room_type_id, stay_date, units_total, units_booked, is_blocked, updated_at)
SELECT :room_type_id, d.day::date, :default_units, :units, false, now()
  -- CAST rather than `:start::date`: SQLAlchemy's bind-parameter parser
  -- cannot tell `:start` from the `::` cast operator and leaves the
  -- parameter unsubstituted.
  FROM generate_series(CAST(:start AS date), CAST(:end AS date), '1 day') AS d(day)
 ORDER BY d.day
ON CONFLICT (room_type_id, stay_date) DO UPDATE
   SET units_booked = room_inventory.units_booked + EXCLUDED.units_booked,
       updated_at   = now()
 WHERE NOT room_inventory.is_blocked
RETURNING stay_date
"""

_RELEASE_SQL = """
UPDATE room_inventory
   SET units_booked = GREATEST(0, units_booked - :units),
       updated_at   = now()
 WHERE room_type_id = :room_type_id
   AND stay_date >= :start
   AND stay_date <  :end
"""


@dataclass(slots=True)
class SqlInventoryService:
    session: AsyncSession

    async def hold(
        self,
        room_type_id: uuid.UUID,
        span: DateRange,
        *,
        units: int,
        default_units: int,
    ) -> HoldResult:
        """Atomically claim inventory for every night of a stay.

        **This is where overbooking is prevented, and it is the only place.**

        The tempting implementation is "check availability, then write". That
        is a check-then-act race: two guests read "1 room left" in the same
        millisecond and both write. No amount of application-level care closes
        that window, because the window is *between* two statements.

        So there is no check. The write itself is the check:

        1. One statement claims all N nights. Nights with no row get one
           (inventory is sparse — no row means available at the room-type
           default); nights with a row have ``units_booked`` incremented.
        2. The ``CHECK (units_booked <= units_total)`` constraint rejects the
           whole statement if *any* night would go over. Postgres evaluates it
           per row, and one violation aborts the transaction — so a stay is
           held entirely or not at all, with no partial hold to unwind.
        3. ``WHERE NOT room_inventory.is_blocked`` on the conflict branch means
           a vendor-blocked night silently updates nothing, which shows up as a
           short RETURNING list and is treated as a refusal.

        **Deadlock avoidance.** Two bookings over overlapping dates take the
        same row locks. Without a consistent order — booking A locking the
        14th then the 15th while booking B locks the 15th then the 14th — they
        deadlock, and Postgres kills one at random. ``ORDER BY d.day`` in the
        SELECT gives every caller the same lock order, so they queue instead.

        The caller owns the transaction. Nothing is committed here, which is
        what makes "the booking row and the inventory it holds are written
        together, or neither is" true.
        """
        params = {
            "room_type_id": room_type_id,
            # DateRange is half-open; generate_series is inclusive.
            "start": span.start,
            "end": span.end - _ONE_DAY,
            "units": units,
            "default_units": default_units,
        }

        # A SAVEPOINT so a constraint violation does not poison the caller's
        # transaction — the booking use case wants to turn this into a 409, not
        # lose everything else it has done.
        #
        # The `try` wraps the `async with`, NOT the body. Catching inside would
        # let the context manager exit normally and issue RELEASE SAVEPOINT on
        # a transaction Postgres has already aborted, which fails with
        # "current transaction is aborted". Letting the exception propagate out
        # of the block is what makes SQLAlchemy emit ROLLBACK TO SAVEPOINT
        # instead.
        try:
            async with self.session.begin_nested():
                result = await self.session.execute(text(_HOLD_SQL), params)
                granted_nights = [row[0] for row in result.all()]
        except IntegrityError:
            # `units_booked <= units_total` fired: some night is full. The
            # savepoint unwound only this statement, so the caller's
            # transaction survives and can turn this into a 409.
            logger.info(
                "inventory_hold_rejected",
                room_type_id=str(room_type_id),
                reason="capacity",
                nights=span.night_count,
            )
            return HoldResult(granted=False, unavailable_dates=tuple(span.nights_iter()))

        if len(granted_nights) != span.night_count:
            # Some night was blocked by the vendor, so its conflict branch
            # matched nothing. Roll the partial claim back by releasing it.
            missing = sorted(set(span.nights_iter()) - set(granted_nights))
            await self.release(room_type_id, span, units=units)
            logger.info(
                "inventory_hold_rejected",
                room_type_id=str(room_type_id),
                reason="blocked",
                blocked_nights=len(missing),
            )
            return HoldResult(granted=False, unavailable_dates=tuple(missing))

        logger.info(
            "inventory_held",
            room_type_id=str(room_type_id),
            nights=span.night_count,
            units=units,
        )
        return HoldResult(granted=True)

    async def release(self, room_type_id: uuid.UUID, span: DateRange, *, units: int) -> int:
        """Give inventory back.

        ``GREATEST(0, ...)`` clamps rather than trusting the arithmetic. A
        double release — a cancellation racing the expiry job — must not drive
        ``units_booked`` negative and quietly create phantom inventory. Both
        paths are idempotent in effect.
        """
        result = await self.session.execute(
            text(_RELEASE_SQL),
            {
                "room_type_id": room_type_id,
                "start": span.start,
                "end": span.end,
                "units": units,
            },
        )
        released = int(cast("CursorResult[Any]", result).rowcount or 0)
        logger.info(
            "inventory_released",
            room_type_id=str(room_type_id),
            nights=released,
            units=units,
        )
        return released

    async def availability(
        self, room_type_id: uuid.UUID, span: DateRange, *, default_units: int
    ) -> Sequence[date]:
        """Nights with nothing free.

        **Advisory only.** It is stale the moment it returns, and a booking
        decision made on it would be exactly the check-then-act race that
        :meth:`hold` exists to avoid. Use it to render a calendar or to explain
        a refusal — never to authorise one.
        """
        rows = (
            (
                await self.session.execute(
                    select(RoomInventoryModel.stay_date).where(
                        RoomInventoryModel.room_type_id == room_type_id,
                        RoomInventoryModel.stay_date >= span.start,
                        RoomInventoryModel.stay_date < span.end,
                        (
                            RoomInventoryModel.is_blocked
                            | (RoomInventoryModel.units_booked >= RoomInventoryModel.units_total)
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        return list(rows)


@dataclass(slots=True)
class SqlRatingWriter:
    """Implements :class:`app.modules.property.public.contract.RatingWriter`."""

    session: AsyncSession

    async def set_rating(self, property_id: uuid.UUID, *, average: float, count: int) -> None:
        # Runs in the caller's transaction, so a review and the rating it moves
        # commit together. A rating that advanced for a review that rolled back
        # is a number nobody can reproduce.
        await self.session.execute(
            text(
                "UPDATE properties "
                "   SET review_average = :average, review_count = :count "
                " WHERE id = :property_id"
            ),
            {"average": average, "count": count, "property_id": property_id},
        )
