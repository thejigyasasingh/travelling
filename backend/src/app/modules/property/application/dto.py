"""Property DTOs.

The search types carry most of the design weight here — everything else is a
straightforward carrier. Read :class:`SearchCriteria` and :class:`SearchSort`
together with ``infrastructure/search_repository.py``; the shape of the query
is visible in the shape of these types.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from app.core.types.date_range import DateRange
from app.core.types.pagination import Cursor
from app.modules.property.domain.value_objects import (
    CancellationPolicy,
    GeoPoint,
    Occupancy,
    PropertyType,
)

# ══════════════════════════════════════════════════════════════════════════
# Search
# ══════════════════════════════════════════════════════════════════════════

#: Widest radius a single search may cover. Beyond this the result set stops
#: being "places near you" and the spatial index stops helping — the planner
#: falls back to a scan and the query gets slower the more it returns.
MAX_SEARCH_RADIUS_M = 100_000
DEFAULT_SEARCH_RADIUS_M = 25_000


class SearchSort(StrEnum):
    """Sort orders, each backed by a specific index.

    Adding one means adding an index; a sort the database cannot satisfy from
    an index becomes a full sort of the whole result set, which is fine at a
    thousand properties and fatal at a million.
    """

    #: Default. Blends rating, review volume and distance — see
    #: `_RELEVANCE_SQL` in the search repository.
    RELEVANCE = "relevance"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    RATING_DESC = "rating_desc"
    DISTANCE_ASC = "distance_asc"
    NEWEST = "newest"


@dataclass(frozen=True, slots=True)
class SearchCriteria:
    """Everything a guest can ask for.

    Every field is optional. A search with nothing set is valid and returns
    popular published listings — which is exactly what the home page needs, and
    what an empty filter panel should produce rather than an error.
    """

    # ── where ─────────────────────────────────────────────────────────────
    query: str | None = None  # free text: property name, city, landmark
    city_id: uuid.UUID | None = None
    near: GeoPoint | None = None
    radius_m: int = DEFAULT_SEARCH_RADIUS_M
    #: Map viewport (SW and NE corners). Takes precedence over `near` — a user
    #: panning a map is asking about what is on screen, not about a radius.
    bounds: tuple[GeoPoint, GeoPoint] | None = None

    # ── when and who ──────────────────────────────────────────────────────
    stay: DateRange | None = None
    occupancy: Occupancy = field(default_factory=Occupancy)
    rooms: int = 1

    # ── filters ───────────────────────────────────────────────────────────
    property_types: frozenset[PropertyType] = frozenset()
    #: ALL of these must be present. A guest who ticks "pool" and "pet
    #: friendly" wants both; ANY would return places with neither of the
    #: combinations they care about.
    amenity_codes: frozenset[str] = frozenset()
    min_price_minor: int | None = None
    max_price_minor: int | None = None
    min_rating: Decimal | None = None
    instant_booking_only: bool = False
    cancellation_policies: frozenset[CancellationPolicy] = frozenset()
    #: Vendor-facing search reuses this type; `include_unpublished` is set only
    #: for a vendor listing their own inventory, never for a guest.
    vendor_id: uuid.UUID | None = None
    include_unpublished: bool = False

    # ── result shaping ────────────────────────────────────────────────────
    sort: SearchSort = SearchSort.RELEVANCE
    limit: int = 20
    cursor: Cursor | None = None

    @property
    def has_dates(self) -> bool:
        return self.stay is not None

    @property
    def effective_radius_m(self) -> int:
        return min(max(self.radius_m, 100), MAX_SEARCH_RADIUS_M)


@dataclass(frozen=True, slots=True)
class SearchResultItem:
    """One search card.

    Flat and denormalised on purpose. A search page renders 20 of these; if
    each needed a follow-up query for its cover image or its cheapest rate,
    one search would be 41 round trips. Everything here comes out of a single
    statement.
    """

    id: uuid.UUID
    slug: str
    name: str
    property_type: str
    city: str
    country_code: str
    #: Approximate until the guest books — see `GeoPoint.obfuscated`.
    latitude: float | None
    longitude: float | None
    distance_m: float | None
    cover_image_key: str | None
    review_average: float
    review_count: int
    amenity_codes: list[str]
    instant_booking: bool
    cancellation_policy: str
    max_occupancy: int
    #: Per night, and inclusive of fees when dates were supplied — see
    #: `Quote.average_nightly` for why the headline number is not the bare rate.
    from_price_minor: int | None
    total_price_minor: int | None
    currency: str
    #: Only meaningful when the search carried dates.
    is_available: bool = True


@dataclass(frozen=True, slots=True)
class SearchResults:
    items: list[SearchResultItem]
    next_cursor: str | None = None
    #: Deliberately approximate above a threshold — an exact count over a
    #: filtered million-row set is a full index scan on every keystroke.
    total_estimate: int | None = None
    applied_radius_m: int | None = None


# ══════════════════════════════════════════════════════════════════════════
# Detail
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ImageView:
    id: uuid.UUID
    url: str
    position: int
    is_cover: bool
    alt_text: str | None = None
    caption: str | None = None


@dataclass(frozen=True, slots=True)
class RoomTypeView:
    id: uuid.UUID
    name: str
    description: str | None
    bed_type: str
    max_adults: int
    max_children: int
    total_units: int
    size_sqft: int | None
    amenity_codes: list[str]
    base_rate_minor: int
    currency: str
    min_nights: int
    #: Populated only when the request carried dates.
    units_available: int | None = None
    quote_total_minor: int | None = None
    quote_breakdown: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class PropertyView:
    id: uuid.UUID
    slug: str
    name: str
    property_type: str
    status: str
    description: str
    #: Exact street address only after a confirmed booking; otherwise the
    #: city-level approximation.
    address: str
    city: str
    state: str | None
    country_code: str
    latitude: float | None
    longitude: float | None
    location_is_approximate: bool
    amenity_codes: list[str]
    images: list[ImageView]
    room_types: list[RoomTypeView]
    cancellation_policy: str
    check_in_from: str
    check_out_by: str
    house_rules: list[str]
    instant_booking: bool
    review_average: float
    review_count: int
    currency: str
    vendor_id: uuid.UUID
    published_at: datetime | None = None
    #: Vendor and admin views only.
    missing_for_publication: list[str] | None = None
    rejection_reason: str | None = None


# ══════════════════════════════════════════════════════════════════════════
# Calendar
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class CalendarDay:
    stay_date: date
    units_total: int
    units_booked: int
    units_available: int
    is_blocked: bool
    rate_minor: int
    rate_source: str  # override | weekend | base
    min_nights: int
    #: True when no row exists for this date and the values are the room-type
    #: defaults. Lets the UI distinguish "not customised" from "set to this".
    is_default: bool


@dataclass(frozen=True, slots=True)
class CalendarView:
    room_type_id: uuid.UUID
    room_type_name: str
    currency: str
    from_date: date
    to_date: date
    days: list[CalendarDay]


# ══════════════════════════════════════════════════════════════════════════
# Inputs
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class CreatePropertyInput:
    name: str
    property_type: str
    line1: str
    city: str
    country_code: str
    state: str | None = None
    line2: str | None = None
    postal_code: str | None = None
    landmark: str | None = None
    description: str = ""
    latitude: float | None = None
    longitude: float | None = None
    currency: str = "INR"
    city_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class UpdatePropertyInput:
    property_id: uuid.UUID
    name: str | None = None
    description: str | None = None
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    country_code: str | None = None
    postal_code: str | None = None
    landmark: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    amenity_codes: list[str] | None = None
    cancellation_policy: str | None = None
    check_in_from: str | None = None
    check_out_by: str | None = None
    house_rules: list[str] | None = None
    instant_booking: bool | None = None
    city_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class CreateRoomTypeInput:
    property_id: uuid.UUID
    name: str
    base_rate_minor: int
    max_adults: int = 2
    max_children: int = 0
    total_units: int = 1
    bed_type: str = "double"
    description: str | None = None
    size_sqft: int | None = None
    amenity_codes: list[str] = field(default_factory=list)
    weekend_rate_minor: int | None = None
    extra_guest_rate_minor: int | None = None
    included_guests: int = 2
    min_nights: int = 1
    max_nights: int = 30
    cleaning_fee_minor: int | None = None
    tax_rate: str = "0.12"


@dataclass(frozen=True, slots=True)
class UpdateRoomTypeInput:
    property_id: uuid.UUID
    room_type_id: uuid.UUID
    name: str | None = None
    description: str | None = None
    base_rate_minor: int | None = None
    weekend_rate_minor: int | None = None
    extra_guest_rate_minor: int | None = None
    included_guests: int | None = None
    max_adults: int | None = None
    max_children: int | None = None
    total_units: int | None = None
    min_nights: int | None = None
    max_nights: int | None = None
    cleaning_fee_minor: int | None = None
    size_sqft: int | None = None
    amenity_codes: list[str] | None = None


@dataclass(frozen=True, slots=True)
class RequestImageUploadInput:
    property_id: uuid.UUID
    filenames: list[str]
    content_types: list[str]


@dataclass(frozen=True, slots=True)
class ConfirmImageInput:
    property_id: uuid.UUID
    storage_keys: list[str]
    alt_texts: list[str | None] | None = None


@dataclass(frozen=True, slots=True)
class SetRatesInput:
    """A bulk calendar edit.

    Ranged rather than per-date because that is how vendors actually think —
    "₹12,000 for all of December" — and because 31 separate requests would be
    31 transactions and 31 cache invalidations.
    """

    property_id: uuid.UUID
    room_type_id: uuid.UUID
    from_date: date
    to_date: date
    rate_minor: int | None = None
    min_nights: int | None = None
    #: Restricts the edit to specific weekdays (0=Mon). "₹15,000 on weekends
    #: in December" in one call.
    weekdays: list[int] | None = None


@dataclass(frozen=True, slots=True)
class SetAvailabilityInput:
    property_id: uuid.UUID
    room_type_id: uuid.UUID
    from_date: date
    to_date: date
    is_blocked: bool | None = None
    units_total: int | None = None


@dataclass(frozen=True, slots=True)
class ReviewPropertyInput:
    property_id: uuid.UUID
    approve: bool
    reason: str | None = None
