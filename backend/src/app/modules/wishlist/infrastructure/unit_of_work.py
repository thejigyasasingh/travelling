"""The wishlist transaction scope."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.property.public import build_property_catalog
from app.modules.wishlist.infrastructure.repositories import SqlWishlistRepository


class WishlistUow:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.items = SqlWishlistRepository(session)
        # The catalogue on the same session, so the existence check that gates
        # a save and the save itself see one consistent snapshot. A property
        # unpublished between the two would otherwise be saveable.
        self.catalog = build_property_catalog(session)

    async def flush(self) -> None:
        await self.items.flush()

    async def commit(self) -> None:
        await self.session.commit()

    def pending_events(self) -> list[Any]:
        """Nothing here is worth an event.

        Saving a property is not a fact another module acts on, and an outbox
        row per heart tap is a lot of write amplification for an analytics
        signal that belongs in the analytics pipeline.
        """
        return []
