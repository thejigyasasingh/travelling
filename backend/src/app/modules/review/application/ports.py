"""What the review use cases need from persistence."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from app.modules.review.domain.entities import Review


class ReviewRepository(Protocol):
    async def get(self, review_id: uuid.UUID) -> Review | None: ...

    async def get_for_booking(self, booking_id: uuid.UUID) -> Review | None:
        """One booking, one review — this is how that is checked before the
        unique constraint has to."""
        ...

    async def add(self, review: Review) -> None: ...

    async def apply_to_rating(
        self, *, property_id: uuid.UUID, rating: int, delta: int
    ) -> tuple[int, float]:
        """Fold one review into the property's aggregate, returning the new
        count and average.

        `delta` is +1 when a review lands and -1 when one is removed, so the
        same call serves both. The arithmetic is an upsert in the database
        rather than a read-modify-write, because two reviews landing on one
        property in the same instant must both count.
        """
        ...

    async def summary(self, property_id: uuid.UUID) -> dict[str, Any] | None: ...

    async def list_for_property(
        self,
        property_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
        sort: str = "recent",
    ) -> tuple[list[Review], int]: ...

    async def list_for_author(self, author_id: uuid.UUID, *, limit: int = 50) -> list[Review]: ...

    async def list_for_vendor(
        self,
        vendor_id: uuid.UUID,
        *,
        awaiting_reply: bool = False,
        property_id: uuid.UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Review], int]: ...

    async def vendor_summary(self, vendor_id: uuid.UUID) -> dict[str, Any]: ...
