"""Property and calendar repositories.

Same identity-map pattern as the auth module: aggregates handed out are
tracked, and ``flush()`` writes them back, so a use case mutates and returns
without an explicit ``save()`` that someone will eventually forget.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.core.types.date_range import DateRange
from app.core.types.money import Money
from app.modules.property.domain import errors
from app.modules.property.domain.availability import (
    AvailabilityWindow,
    DayAvailability,
    build_window,
)
from app.modules.property.domain.entities import Property
from app.modules.property.infrastructure import mappers
from app.modules.property.infrastructure.models import (
    AmenityModel,
    PropertyModel,
    RoomInventoryModel,
    RoomTypeModel,
)

logger = get_logger(__name__)


def _affected(result: Any) -> int:
    return int(cast("CursorResult[Any]", result).rowcount or 0)


class SqlPropertyRepository:
    """Implements
    :class:`app.modules.property.application.ports.PropertyRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._identity: dict[uuid.UUID, tuple[Property, PropertyModel]] = {}

    # ── reads ─────────────────────────────────────────────────────────────

    async def get(self, property_id: uuid.UUID) -> Property | None:
        if property_id in self._identity:
            return self._identity[property_id][0]
        stmt = select(PropertyModel).where(
            PropertyModel.id == property_id, PropertyModel.deleted_at.is_(None)
        )
        return self._track((await self._session.execute(stmt)).scalar_one_or_none())

    async def get_for_vendor(self, property_id: uuid.UUID, vendor_id: uuid.UUID) -> Property | None:
        """Scoped at the query, so a property belonging to another vendor is
        simply not found — the interface turns that into 404, never 403, which
        would confirm the id exists."""
        stmt = select(PropertyModel).where(
            PropertyModel.id == property_id,
            PropertyModel.vendor_id == vendor_id,
            PropertyModel.deleted_at.is_(None),
        )
        return self._track((await self._session.execute(stmt)).scalar_one_or_none())

    async def get_published(self, property_id: uuid.UUID) -> Property | None:
        stmt = select(PropertyModel).where(
            PropertyModel.id == property_id,
            PropertyModel.status == "published",
            PropertyModel.deleted_at.is_(None),
        )
        return self._track((await self._session.execute(stmt)).scalar_one_or_none())

    async def get_by_slug(self, slug: str) -> Property | None:
        stmt = select(PropertyModel).where(
            PropertyModel.slug == slug,
            PropertyModel.status == "published",
            PropertyModel.deleted_at.is_(None),
        )
        return self._track((await self._session.execute(stmt)).scalar_one_or_none())

    async def slug_exists(self, slug: str) -> bool:
        stmt = select(PropertyModel.id).where(
            PropertyModel.slug == slug, PropertyModel.deleted_at.is_(None)
        )
        return (await self._session.execute(stmt)).first() is not None

    async def list_for_vendor(
        self, vendor_id: uuid.UUID, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[Property], int]:
        """Vendor dashboard.

        Offset paging is right here and wrong for search: this set is one
        vendor's portfolio — small, bounded, and the vendor wants page numbers.
        """
        conditions = [
            PropertyModel.vendor_id == vendor_id,
            PropertyModel.deleted_at.is_(None),
        ]
        if status:
            conditions.append(PropertyModel.status == status)

        total = (
            await self._session.execute(
                select(func.count()).select_from(PropertyModel).where(*conditions)
            )
        ).scalar() or 0

        rows = (
            (
                await self._session.execute(
                    select(PropertyModel)
                    .where(*conditions)
                    .order_by(PropertyModel.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return [mappers.property_to_domain(row) for row in rows], int(total)

    # ── writes ────────────────────────────────────────────────────────────

    async def add(self, prop: Property) -> None:
        row = mappers.property_to_model(prop)
        self._session.add(row)
        self._identity[prop.id] = (prop, row)

    async def soft_delete(self, prop: Property, *, by: uuid.UUID | None) -> None:
        """Never a hard delete — bookings, invoices and payouts reference this
        row for years, and tax law requires them to stay reconstructable."""
        row = self._identity.get(prop.id, (None, None))[1]
        if row is None:  # pragma: no cover — callers always load first
            row = await self._session.get(PropertyModel, prop.id)
        if row is not None:
            row.deleted_at = utcnow()
            row.deleted_by = by
            # Leaving it published would keep it in search until the next
            # reindex, which is a live listing nobody can book.
            row.status = "unpublished"

    async def flush(self) -> None:
        for prop, row in self._identity.values():
            mappers.apply_property_to_model(prop, row)
        await self._session.flush()

    def pending_events(self) -> list[Any]:
        events: list[Any] = []
        for prop, _ in self._identity.values():
            events.extend(prop.pull_events())
        return events

    def _track(self, row: PropertyModel | None) -> Property | None:
        if row is None:
            return None
        if row.id in self._identity:
            return self._identity[row.id][0]
        prop = mappers.property_to_domain(row)
        self._identity[row.id] = (prop, row)
        return prop


class SqlCalendarRepository:
    """The sparse inventory and rate rows.

    Every read densifies against the room-type default; every write persists
    only dates that deviate. See ``domain/availability.py``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def window(
        self, room_type_id: uuid.UUID, span: DateRange, *, default_units: int
    ) -> AvailabilityWindow:
        rows = (
            (
                await self._session.execute(
                    select(RoomInventoryModel).where(
                        RoomInventoryModel.room_type_id == room_type_id,
                        RoomInventoryModel.stay_date >= span.start,
                        RoomInventoryModel.stay_date < span.end,
                    )
                )
            )
            .scalars()
            .all()
        )
        existing = {
            row.stay_date: DayAvailability(
                stay_date=row.stay_date,
                units_total=row.units_total,
                units_booked=row.units_booked,
                is_blocked=row.is_blocked,
                rate_override_minor=row.rate_override_minor,
                min_nights_override=row.min_nights_override,
            )
            for row in rows
        }
        return build_window(
            room_type_id=room_type_id,
            span=span,
            default_units=default_units,
            rows=existing,
        )

    async def windows_for_property(
        self, property_id: uuid.UUID, span: DateRange
    ) -> dict[uuid.UUID, AvailabilityWindow]:
        """Every room type's calendar in **two** queries, not two per room.

        The vendor's month view asks for all of them at once; one query per
        room type would be an N+1 that grows with the property's size.
        """
        rooms = (
            await self._session.execute(
                select(RoomTypeModel.id, RoomTypeModel.total_units).where(
                    RoomTypeModel.property_id == property_id,
                    RoomTypeModel.deleted_at.is_(None),
                )
            )
        ).all()
        if not rooms:
            return {}

        room_ids = [r[0] for r in rooms]
        rows = (
            (
                await self._session.execute(
                    select(RoomInventoryModel).where(
                        RoomInventoryModel.room_type_id.in_(room_ids),
                        RoomInventoryModel.stay_date >= span.start,
                        RoomInventoryModel.stay_date < span.end,
                    )
                )
            )
            .scalars()
            .all()
        )

        by_room: dict[uuid.UUID, dict[date, DayAvailability]] = {rid: {} for rid in room_ids}
        for row in rows:
            by_room[row.room_type_id][row.stay_date] = DayAvailability(
                stay_date=row.stay_date,
                units_total=row.units_total,
                units_booked=row.units_booked,
                is_blocked=row.is_blocked,
                rate_override_minor=row.rate_override_minor,
                min_nights_override=row.min_nights_override,
            )

        return {
            room_id: build_window(
                room_type_id=room_id,
                span=span,
                default_units=default_units,
                rows=by_room[room_id],
            )
            for room_id, default_units in rooms
        }

    async def rate_overrides(
        self, room_type_id: uuid.UUID, span: DateRange
    ) -> Mapping[date, Money]:
        rows = (
            await self._session.execute(
                select(RoomInventoryModel.stay_date, RoomInventoryModel.rate_override_minor).where(
                    RoomInventoryModel.room_type_id == room_type_id,
                    RoomInventoryModel.stay_date >= span.start,
                    RoomInventoryModel.stay_date < span.end,
                    RoomInventoryModel.rate_override_minor.isnot(None),
                )
            )
        ).all()
        currency = await self._currency_for(room_type_id)
        return {row[0]: Money(row[1], currency) for row in rows}

    async def upsert_days(
        self, room_type_id: uuid.UUID, days: Sequence[DayAvailability], *, currency: str
    ) -> int:
        """Write calendar rows.

        ``units_booked`` is deliberately **not** in the update set. It belongs
        to the booking module, and a vendor's calendar edit arriving between a
        booking's read and write must not overwrite it — that is precisely how
        a confirmed reservation silently disappears.
        """
        if not days:
            return 0

        payload = [
            {
                "room_type_id": room_type_id,
                "stay_date": day.stay_date,
                "units_total": day.units_total,
                "units_booked": day.units_booked,
                "is_blocked": day.is_blocked,
                "rate_override_minor": day.rate_override_minor,
                "min_nights_override": day.min_nights_override,
                "updated_at": utcnow(),
            }
            for day in days
        ]
        stmt = pg_insert(RoomInventoryModel).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=["room_type_id", "stay_date"],
            set_={
                "units_total": stmt.excluded.units_total,
                "is_blocked": stmt.excluded.is_blocked,
                "rate_override_minor": stmt.excluded.rate_override_minor,
                "min_nights_override": stmt.excluded.min_nights_override,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        return _affected(await self._session.execute(stmt))

    async def set_rates(
        self,
        room_type_id: uuid.UUID,
        span: DateRange,
        *,
        rate: Money | None,
        min_nights: int | None,
        weekdays: frozenset[int] | None,
        default_units: int,
    ) -> int:
        """Set or clear rate overrides across a range.

        ``generate_series`` builds the dates in Postgres rather than shipping
        90 parameter sets from Python — one statement, one round trip, and the
        planner can see the whole thing.
        """
        params: dict[str, Any] = {
            "room_type_id": room_type_id,
            "start": span.start,
            "end": span.end - timedelta(days=1),  # DateRange is half-open
            "rate": rate.amount_minor if rate else None,
            "min_nights": min_nights,
            "default_units": default_units,
        }
        weekday_clause = ""
        if weekdays:
            # Postgres DOW is 0=Sunday; Python weekday() is 0=Monday.
            params["dows"] = sorted((wd + 1) % 7 for wd in weekdays)
            weekday_clause = "WHERE EXTRACT(DOW FROM d.day)::int = ANY(:dows)"

        sql = f"""
            INSERT INTO room_inventory
                (room_type_id, stay_date, units_total, units_booked, is_blocked,
                 rate_override_minor, min_nights_override, updated_at)
            SELECT :room_type_id, d.day::date, :default_units, 0, false,
                   :rate, :min_nights, now()
              -- CAST, not `:start::date` — see the note in public/adapters.py.
              FROM generate_series(CAST(:start AS date), CAST(:end AS date), '1 day') AS d(day)
            {weekday_clause}
            ON CONFLICT (room_type_id, stay_date) DO UPDATE
               SET rate_override_minor = EXCLUDED.rate_override_minor,
                   min_nights_override = COALESCE(EXCLUDED.min_nights_override,
                                                  room_inventory.min_nights_override),
                   updated_at = now()
        """
        return _affected(await self._session.execute(text(sql), params))

    async def purge_past(self, *, before: date) -> int:
        """Nightly cleanup. Nothing can be booked into a past date and no
        report reads these rows."""
        return _affected(
            await self._session.execute(
                delete(RoomInventoryModel).where(RoomInventoryModel.stay_date < before)
            )
        )

    async def _currency_for(self, room_type_id: uuid.UUID) -> str:
        row = (
            await self._session.execute(
                select(PropertyModel.currency)
                .join(RoomTypeModel, RoomTypeModel.property_id == PropertyModel.id)
                .where(RoomTypeModel.id == room_type_id)
            )
        ).scalar()
        return row or "INR"


class SqlAmenityCatalog:
    """Validates amenity codes.

    The catalogue changes a few times a year and is read on every listing edit
    and every search, so it is cached in the process after the first read. A
    deploy clears it; that is frequent enough for a table that changes
    seasonally.
    """

    _cache: frozenset[str] | None = None

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def known_codes(self) -> frozenset[str]:
        if SqlAmenityCatalog._cache is None:
            rows = (await self._session.execute(select(AmenityModel.code))).scalars().all()
            SqlAmenityCatalog._cache = frozenset(rows)
        return SqlAmenityCatalog._cache

    async def validate(self, codes: frozenset[str]) -> None:
        if not codes:
            return
        unknown = codes - await self.known_codes()
        if unknown:
            # Every unknown code at once, so a vendor fixing a list of twenty
            # does not discover them one request at a time.
            raise errors.UnknownAmenityError(sorted(unknown))

    async def describe(self, codes: Sequence[str]) -> list[dict[str, Any]]:
        if not codes:
            return []
        rows = (
            (
                await self._session.execute(
                    select(AmenityModel)
                    .where(AmenityModel.code.in_(list(codes)))
                    .order_by(AmenityModel.category, AmenityModel.sort_order)
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "code": row.code,
                "label": row.label,
                "category": row.category,
                "icon": row.icon,
            }
            for row in rows
        ]

    @classmethod
    def invalidate(cls) -> None:
        """Called after an admin edits the catalogue."""
        cls._cache = None


class CdnImageUrlBuilder:
    """Storage key → browser-loadable URL.

    Listing photos are **public and CDN-served**, deliberately not presigned. A
    distinct signed URL per user would defeat CDN caching entirely — every
    request a cache miss, every image paid for again — and these are marketing
    photos the vendor wants seen.

    Private documents (vendor KYC, invoices) go through
    ``S3Storage.presign_download`` instead.
    """

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    def public_url(self, key: str) -> str:
        return f"{self._base}/{key.lstrip('/')}"


def utc_now() -> datetime:  # pragma: no cover — re-exported for the calendar job
    return utcnow()
