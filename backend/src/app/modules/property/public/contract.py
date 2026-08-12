"""The property module's published contract — types and protocols.

See ``public/__init__.py`` for why this boundary exists. Everything here is
either a flat read model or a protocol; no aggregate crosses the line.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.core.types.date_range import DateRange
from app.core.types.money import Money
from app.modules.property.domain.pricing import RateConfig, quote_stay
from app.modules.property.domain.value_objects import Occupancy

#: Pricing, re-exported. Booking must produce the same number the guest was
#: quoted, and the only way to guarantee that is to run the same code.
price_stay = quote_stay


@dataclass(frozen=True, slots=True)
class RoomSnapshot:
    """One room type, as booking needs to see it.

    A snapshot, not a reference. The booking records what the rules *were* at
    the moment of booking; a vendor later changing their minimum stay or
    cancellation policy must not retroactively alter a confirmed reservation.
    """

    id: uuid.UUID
    property_id: uuid.UUID
    name: str
    total_units: int
    max_adults: int
    max_children: int
    rate: RateConfig

    @property
    def max_billable_guests(self) -> int:
        return self.max_adults + self.max_children

    def accommodates(self, occupancy: Occupancy) -> bool:
        return occupancy.billable_guests <= self.max_billable_guests


@dataclass(frozen=True, slots=True)
class PropertySnapshot:
    id: uuid.UUID
    vendor_id: uuid.UUID
    name: str
    slug: str
    property_type: str
    city: str
    country_code: str
    currency: str
    #: Named policy, not free text — the refund engine switches on it.
    cancellation_policy: str
    check_in_from: str
    check_out_by: str
    #: False means the vendor approves each request. The booking then waits in
    #: `pending_approval` rather than going straight to payment.
    instant_booking: bool
    is_bookable: bool
    rooms: tuple[RoomSnapshot, ...]
    #: Only shown to the guest once the booking is confirmed.
    full_address: str

    def room(self, room_type_id: uuid.UUID) -> RoomSnapshot | None:
        return next((r for r in self.rooms if r.id == room_type_id), None)


@dataclass(frozen=True, slots=True)
class PropertyCard:
    """A listing as it appears in a list — a search result, a wishlist, a rail.

    Distinct from :class:`PropertySnapshot`, which is booking-shaped: rooms,
    policies, addresses. This is display-shaped, and the difference is not
    cosmetic. A card carries a *price* and a *rating*, which snapshot
    deliberately does not, and both of those are read live rather than stored
    by the caller — a wishlist showing a price from the month it was saved is
    a wishlist that misleads someone into clicking.
    """

    id: uuid.UUID
    slug: str
    name: str
    city: str
    country_code: str
    currency: str
    cover_image_url: str | None
    #: Cheapest room's nightly rate, in minor units. `None` for a listing with
    #: no rooms priced yet.
    from_price_minor: int | None
    review_average: float
    review_count: int
    #: False when the listing is unpublished, suspended or deleted. Returned
    #: rather than omitted so a caller holding the id — someone who saved it —
    #: can render "no longer available" instead of a silently shorter list.
    is_live: bool


class PropertyCatalog(Protocol):
    """Read access to bookable inventory."""

    async def cards(self, property_ids: Sequence[uuid.UUID]) -> Mapping[uuid.UUID, PropertyCard]:
        """Batch display data, keyed by id.

        Batch because every caller has a list: one query for twenty saved
        properties rather than twenty. Missing ids are simply absent from the
        mapping — a hard-deleted property is gone, and the caller decides
        whether that is an error or a row to drop.

        Includes non-live listings, flagged. Safe because the caller already
        holds the id; this is not a discovery surface and must not be used as
        one.
        """
        ...

    async def snapshot(self, property_id: uuid.UUID) -> PropertySnapshot | None:
        """Published properties only. A draft or suspended listing must not be
        bookable through a stale link or a guessed id."""
        ...

    async def rate_overrides(
        self, room_type_id: uuid.UUID, span: DateRange
    ) -> Mapping[date, Money]: ...


@dataclass(frozen=True, slots=True)
class HoldResult:
    """Outcome of an attempt to take inventory."""

    granted: bool
    #: The nights that blocked it, so the guest can be offered alternatives
    #: rather than a bare "unavailable".
    unavailable_dates: tuple[date, ...] = ()


class InventoryService(Protocol):
    """The only way to take or release inventory.

    Every method runs inside the **caller's** transaction. That is what makes
    "the booking row and the inventory it holds are written together, or
    neither is" true — the property module cannot commit on its own and leave
    booking to fail.
    """

    async def hold(
        self,
        room_type_id: uuid.UUID,
        span: DateRange,
        *,
        units: int,
        default_units: int,
    ) -> HoldResult:
        """Atomically claim ``units`` for every night in ``span``.

        Correctness here does not rest on a preceding availability check —
        that would be a check-then-act race with a window no amount of care
        closes. It rests on a database CHECK constraint; see the implementation
        for how, and for why the nights are locked in date order.
        """
        ...

    async def release(self, room_type_id: uuid.UUID, span: DateRange, *, units: int) -> int:
        """Give inventory back. Used on cancellation and on hold expiry."""
        ...

    async def availability(
        self, room_type_id: uuid.UUID, span: DateRange, *, default_units: int
    ) -> Sequence[date]:
        """Nights with nothing free. Advisory only — never the basis of a
        booking decision, because it is stale the moment it returns."""
        ...


class RatingWriter(Protocol):
    """Updates a property's published rating.

    Exists so the review module can keep `properties.review_average` current
    without writing to a table it does not own. The review module computes the
    aggregate — it owns every review — and hands the two numbers here; the
    property module decides what to do with them.

    The alternative, an UPDATE from the review module, would mean two modules
    writing one table and no single place that knows what the columns mean.
    """

    async def set_rating(self, property_id: uuid.UUID, *, average: float, count: int) -> None: ...
