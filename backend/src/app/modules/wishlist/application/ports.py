"""What the wishlist use cases need from persistence."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.modules.wishlist.application.dto import WishlistRow


class WishlistRepository(Protocol):
    async def list_for(self, user_id: uuid.UUID) -> list[WishlistRow]: ...

    async def count_for(self, user_id: uuid.UUID) -> int: ...

    async def exists(self, user_id: uuid.UUID, property_id: uuid.UUID) -> bool: ...

    async def save(
        self,
        *,
        user_id: uuid.UUID,
        property_id: uuid.UUID,
        note: str | None,
        name_snapshot: str,
    ) -> None:
        """Insert, or update the note on an existing save.

        An upsert rather than a check-then-insert: a heart icon gets double
        tapped, and both taps race through any prior read.
        """
        ...

    async def remove(self, user_id: uuid.UUID, property_id: uuid.UUID) -> bool: ...

    async def clear(self, user_id: uuid.UUID) -> int: ...
