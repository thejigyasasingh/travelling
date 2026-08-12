"""Ports for the property module."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any, Protocol

from app.core.types.date_range import DateRange
from app.core.types.money import Money
from app.modules.property.application.dto import SearchCriteria, SearchResults
from app.modules.property.domain.availability import AvailabilityWindow, DayAvailability
from app.modules.property.domain.entities import Property


class PropertyRepository(Protocol):
    async def get(self, property_id: uuid.UUID) -> Property | None:
        """Load the aggregate — property, room types and images.

        One query with joins, not four. A vendor dashboard listing 50
        properties would otherwise fire 150 follow-ups.
        """
        ...

    async def get_for_vendor(self, property_id: uuid.UUID, vendor_id: uuid.UUID) -> Property | None:
        """Scoped load. A property belonging to another vendor resolves to
        ``None``, which the interface turns into 404 — never 403, which would
        confirm the id exists."""
        ...

    async def get_published(self, property_id: uuid.UUID) -> Property | None: ...

    async def get_by_slug(self, slug: str) -> Property | None: ...

    async def add(self, prop: Property) -> None: ...

    async def slug_exists(self, slug: str) -> bool: ...

    async def list_for_vendor(
        self, vendor_id: uuid.UUID, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[Property], int]:
        """Vendor dashboard. Offset paging is correct here: the set is small,
        bounded by one vendor's portfolio, and the vendor wants page numbers."""
        ...

    async def soft_delete(self, prop: Property, *, by: uuid.UUID | None) -> None: ...


class SearchRepository(Protocol):
    """Read-only, and deliberately separate from :class:`PropertyRepository`.

    Search does not hydrate aggregates. It runs one hand-written statement and
    returns flat rows, because building 20 ``Property`` objects — each with its
    room types and images — to render 20 cards is work thrown away. This is the
    CQRS split at its most concrete.
    """

    async def search(self, criteria: SearchCriteria) -> SearchResults: ...

    async def count_estimate(self, criteria: SearchCriteria) -> int: ...

    async def suggest(self, prefix: str, *, limit: int = 8) -> list[dict[str, Any]]:
        """Type-ahead over cities and property names."""
        ...


class CalendarRepository(Protocol):
    """The sparse inventory and rate rows.

    Separate from the property repository because it is a separate aggregate —
    see the note at the top of ``domain/entities.py``.
    """

    async def window(
        self, room_type_id: uuid.UUID, span: DateRange, *, default_units: int
    ) -> AvailabilityWindow:
        """Densify sparse rows against the room-type default."""
        ...

    async def windows_for_property(
        self, property_id: uuid.UUID, span: DateRange
    ) -> dict[uuid.UUID, AvailabilityWindow]: ...

    async def rate_overrides(
        self, room_type_id: uuid.UUID, span: DateRange
    ) -> Mapping[date, Money]: ...

    async def upsert_days(
        self, room_type_id: uuid.UUID, days: Sequence[DayAvailability], *, currency: str
    ) -> int:
        """Write calendar rows.

        Upsert, because a row exists only if the date has ever deviated from
        the default — the caller cannot know whether to INSERT or UPDATE, and
        should not have to ask.
        """
        ...

    async def set_rates(
        self,
        room_type_id: uuid.UUID,
        span: DateRange,
        *,
        rate: Money | None,
        min_nights: int | None,
        weekdays: frozenset[int] | None,
        default_units: int,
    ) -> int: ...

    async def purge_past(self, *, before: date) -> int:
        """Calendar rows for dates that have passed are dead weight — nothing
        can be booked into them and no report reads them."""
        ...


class AmenityCatalog(Protocol):
    """Validates amenity codes against the catalogue.

    Cached in-process: the catalogue changes a few times a year and is read on
    every listing edit and every search.
    """

    async def known_codes(self) -> frozenset[str]: ...

    async def validate(self, codes: frozenset[str]) -> None:
        """Raises :class:`UnknownAmenityError` listing every unknown code."""
        ...

    async def describe(self, codes: Sequence[str]) -> list[dict[str, Any]]: ...


class MediaStorage(Protocol):
    """Presigned direct-to-S3 uploads.

    The API never receives image bytes — see ``infrastructure/storage/s3.py``
    for why proxying a hotel manager's 20 MB photo through a worker is a
    self-inflicted outage.
    """

    async def presign_upload(
        self, key: str, *, content_type: str, max_bytes: int
    ) -> dict[str, Any]: ...

    async def presign_download(self, key: str, *, expires_in: timedelta) -> str: ...

    async def head(self, key: str) -> dict[str, Any] | None:
        """Confirm the upload actually happened, and learn its real size and
        type. The client's claim about what it uploaded is not evidence."""
        ...

    async def delete(self, key: str) -> None: ...

    @staticmethod
    def build_key(*, scope: str, owner_id: uuid.UUID, filename: str) -> str: ...


class ImageUrlBuilder(Protocol):
    """Turns a storage key into something a browser can load.

    A port rather than a helper because the answer differs by environment: a
    CloudFront URL in production, a presigned MinIO URL locally. Public listing
    photos are served from the CDN and are *not* presigned — a distinct signed
    URL per user would defeat CDN caching entirely.
    """

    def public_url(self, key: str) -> str: ...
