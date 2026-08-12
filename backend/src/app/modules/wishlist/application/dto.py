"""What crosses out of the wishlist module."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SavedProperty:
    """One saved listing, assembled from the stored row plus live catalogue
    data. Everything price- or rating-shaped here was read this request."""

    property_id: uuid.UUID
    name: str
    slug: str
    city: str
    country_code: str
    currency: str
    cover_image_url: str | None
    from_price_minor: int | None
    review_average: float
    review_count: int
    #: False when the listing is no longer on sale. The card renders as a
    #: tombstone rather than a link, and carries no price.
    available: bool
    note: str | None
    saved_at: datetime


@dataclass(frozen=True, slots=True)
class WishlistRow:
    """The stored row, before any catalogue data is attached."""

    property_id: uuid.UUID
    name_snapshot: str
    note: str | None
    created_at: datetime
