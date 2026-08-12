"""Property value objects.

Framework-free, so every rule here is testable in milliseconds and enforced
identically whether the caller is an HTTP request, a bulk vendor import, or an
admin CLI command.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Self


class PropertyType(StrEnum):
    """The five inventory types this platform sells.

    Kept as one enum rather than separate aggregates because they differ in
    *presentation and policy*, not in structure — all five have rooms/units,
    rates, availability and photos. Splitting them would mean five near-identical
    search queries and five copies of the pricing engine.

    Where they genuinely differ is captured by :attr:`is_whole_unit`.
    """

    HOTEL = "hotel"
    RESORT = "resort"
    VILLA = "villa"
    APARTMENT = "apartment"
    HOMESTAY = "homestay"

    @property
    def is_whole_unit(self) -> bool:
        """True when the guest books the *entire* place, not a room in it.

        This is the one structural difference that matters. A villa has exactly
        one bookable unit, so "2 rooms available" is meaningless and the
        occupancy limit applies to the whole property. A hotel sells many units
        of each room type independently.
        """
        return self in (PropertyType.VILLA, PropertyType.APARTMENT)

    @property
    def label(self) -> str:
        return self.value.capitalize()


class PropertyStatus(StrEnum):
    """Listing lifecycle.

    The review step is not bureaucracy: a marketplace that lets anyone publish
    inventory instantly gets fraudulent listings, stolen photos and properties
    that do not exist — and the first traveller to arrive at one is a refund, a
    support case and a trust problem that costs far more than the review.
    """

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    #: Vendor-initiated. Reversible, keeps all data — a hotel closing for
    #: monsoon season should not have to re-create its listing in October.
    UNPUBLISHED = "unpublished"
    REJECTED = "rejected"
    #: Admin-initiated, for fraud or a serious guest-safety complaint. Distinct
    #: from `unpublished` so a vendor cannot simply republish.
    SUSPENDED = "suspended"

    @property
    def is_visible(self) -> bool:
        return self is PropertyStatus.PUBLISHED

    @property
    def is_editable_by_vendor(self) -> bool:
        return self in (
            PropertyStatus.DRAFT,
            PropertyStatus.PUBLISHED,
            PropertyStatus.UNPUBLISHED,
            PropertyStatus.REJECTED,
        )


class CancellationPolicy(StrEnum):
    """Named policies, not free-form vendor text.

    A free-text policy cannot be reasoned about by the refund engine, cannot be
    filtered on in search, and cannot be explained consistently to a guest at
    the moment they are deciding whether to book. The refund percentages live
    in the booking module; this is the identifier both sides agree on.
    """

    FLEXIBLE = "flexible"  # full refund up to 24h before check-in
    MODERATE = "moderate"  # full refund up to 5 days before
    STRICT = "strict"  # 50% up to 7 days before
    NON_REFUNDABLE = "non_refundable"


class BedType(StrEnum):
    SINGLE = "single"
    DOUBLE = "double"
    QUEEN = "queen"
    KING = "king"
    BUNK = "bunk"
    SOFA_BED = "sofa_bed"
    FLOOR_MATTRESS = "floor_mattress"


# ══════════════════════════════════════════════════════════════════════════
# Address and location
# ══════════════════════════════════════════════════════════════════════════

_POSTAL_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\s\-]{2,11}$")


@dataclass(frozen=True, slots=True)
class Address:
    """A postal address. Country is ISO-3166 alpha-2, always.

    ``"India"`` vs ``"india"`` vs ``"IN"`` vs ``"Bharat"`` in one column makes
    "how many properties in India?" unanswerable and every country filter a
    guess.
    """

    line1: str
    city: str
    country_code: str
    state: str | None = None
    line2: str | None = None
    postal_code: str | None = None
    landmark: str | None = None

    def __post_init__(self) -> None:
        if not self.line1.strip():
            msg = "Address line 1 is required"
            raise ValueError(msg)
        if not self.city.strip():
            msg = "City is required"
            raise ValueError(msg)
        if len(self.country_code) != 2 or not self.country_code.isalpha():
            msg = f"country_code must be ISO-3166 alpha-2, got {self.country_code!r}"
            raise ValueError(msg)
        if self.postal_code and not _POSTAL_RE.match(self.postal_code):
            msg = f"Postal code {self.postal_code!r} is not plausible"
            raise ValueError(msg)

    @classmethod
    def parse(cls, **kwargs: str | None) -> Self:
        cleaned = {k: (v.strip() if isinstance(v, str) else v) for k, v in kwargs.items()}
        if isinstance(cleaned.get("country_code"), str):
            cleaned["country_code"] = cleaned["country_code"].upper()  # type: ignore[union-attr]
        return cls(**cleaned)  # type: ignore[arg-type]

    @property
    def is_complete(self) -> bool:
        """Enough to publish, and enough for a guest to actually arrive."""
        return bool(self.line1 and self.city and self.country_code and self.postal_code)

    def single_line(self) -> str:
        parts = [self.line1, self.line2, self.city, self.state, self.postal_code]
        return ", ".join(p for p in parts if p)

    def approximate(self) -> str:
        """What an unbooked guest sees.

        The exact street address is revealed only after a booking is confirmed.
        Publishing it lets anyone locate an occupied private home, and it lets
        competitors scrape a vendor's whole portfolio.
        """
        return ", ".join(p for p in (self.city, self.state, self.country_code) if p)


@dataclass(frozen=True, slots=True)
class GeoPoint:
    """WGS-84 coordinate.

    Stored as PostGIS ``geography(Point, 4326)``, not two floats. Geography does
    great-circle distance on a spheroid; two floats and Pythagoras are wrong by
    up to 0.5% at Indian latitudes and catastrophically wrong near the poles or
    across the antimeridian — and cannot use a spatial index at all.
    """

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not -90.0 <= self.latitude <= 90.0:
            msg = f"latitude {self.latitude} is out of range"
            raise ValueError(msg)
        if not -180.0 <= self.longitude <= 180.0:
            msg = f"longitude {self.longitude} is out of range"
            raise ValueError(msg)
        if self.latitude == 0.0 and self.longitude == 0.0:
            # Null Island. Almost always an uninitialised value that would
            # otherwise put a Goa villa in the Gulf of Guinea.
            msg = "Coordinates (0, 0) are almost certainly a mistake"
            raise ValueError(msg)

    def distance_metres(self, other: GeoPoint) -> float:
        """Haversine. For display and tests only.

        Search distance is computed by PostGIS, which can use the spatial
        index; doing it in Python would mean loading every property first.
        """
        radius = 6_371_008.8  # IUGG mean Earth radius
        lat1, lat2 = math.radians(self.latitude), math.radians(other.latitude)
        dlat = lat2 - lat1
        dlon = math.radians(other.longitude - self.longitude)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * radius * math.asin(math.sqrt(a))

    def to_wkt(self) -> str:
        """PostGIS literal. Longitude first — the opposite of how humans say
        it, and a reliable source of properties appearing in the wrong ocean."""
        return f"POINT({self.longitude} {self.latitude})"

    @property
    def obfuscated(self) -> GeoPoint:
        """Coordinates shown before booking.

        Rounded to ~1 km so the map pin lands in the right neighbourhood
        without pinpointing a private home. Deterministic rather than randomly
        jittered: a pin that moves on every page load looks broken, and
        repeated samples of a random jitter average out to the true location.
        """
        return GeoPoint(round(self.latitude, 2), round(self.longitude, 2))


# ══════════════════════════════════════════════════════════════════════════
# Occupancy
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class Occupancy:
    """Who is staying.

    Children and infants are counted separately because they price differently
    and because occupancy limits usually apply to adults only. Collapsing them
    into one "guests" number is how a family of two adults and an infant gets
    told a room sleeping three is too small.
    """

    adults: int = 1
    children: int = 0
    infants: int = 0

    def __post_init__(self) -> None:
        if self.adults < 1:
            msg = "At least one adult is required"
            raise ValueError(msg)
        for field_name, value in (
            ("adults", self.adults),
            ("children", self.children),
            ("infants", self.infants),
        ):
            if value < 0 or value > 30:
                msg = f"{field_name} must be between 0 and 30"
                raise ValueError(msg)

    @property
    def billable_guests(self) -> int:
        """Infants are free everywhere in this market; charging for one is a
        support ticket, not revenue."""
        return self.adults + self.children

    @property
    def total(self) -> int:
        return self.adults + self.children + self.infants


# ══════════════════════════════════════════════════════════════════════════
# Slugs
# ══════════════════════════════════════════════════════════════════════════

_SLUG_STRIP: Final = re.compile(r"[^a-z0-9]+")


def slugify(value: str, *, max_length: int = 80) -> str:
    """URL segment for a property.

    Unicode is transliterated rather than percent-encoded: ``/goa-beach-villa``
    is shareable, indexable and readable in an SMS; ``/%E0%A4%97%E0%A5%8B`` is
    none of those.

    The slug is *not* the identity — the URL carries the id too. A vendor
    renaming their property must not break every link to it.
    """
    normalised = unicodedata.normalize("NFKD", value)
    ascii_only = normalised.encode("ascii", "ignore").decode()
    slug = _SLUG_STRIP.sub("-", ascii_only.lower()).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug or "property"
