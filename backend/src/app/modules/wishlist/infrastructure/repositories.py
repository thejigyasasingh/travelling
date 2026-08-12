"""Wishlist persistence."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.wishlist.application.dto import WishlistRow
from app.modules.wishlist.infrastructure.models import WishlistItemModel

#: Upsert. The conflict target is the unique constraint, so a second save of
#: the same property updates the note instead of raising — which is what makes
#: a double-tapped heart icon a no-op rather than a 409 the UI has to explain.
#:
#: `created_at` is deliberately *not* touched on conflict: the list is ordered
#: by it, and re-saving something should not jump it to the top of a list the
#: guest has arranged.
_UPSERT = text("""
INSERT INTO wishlist_items
    (id, user_id, property_id, note, name_snapshot, created_at, updated_at)
VALUES (gen_random_uuid(), :user_id, :property_id, :note, :name, now(), now())
ON CONFLICT ON CONSTRAINT uq_wishlist_user_property DO UPDATE
   SET note          = EXCLUDED.note,
       name_snapshot = EXCLUDED.name_snapshot,
       updated_at    = now()
""")


class SqlWishlistRepository:
    """Implements :class:`app.modules.wishlist.application.ports.WishlistRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for(self, user_id: uuid.UUID) -> list[WishlistRow]:
        rows = (
            (
                await self._session.execute(
                    select(WishlistItemModel)
                    .where(WishlistItemModel.user_id == user_id)
                    # Newest first: the thing you just saved is the thing you
                    # came back to look at.
                    .order_by(WishlistItemModel.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return [
            WishlistRow(
                property_id=row.property_id,
                name_snapshot=row.name_snapshot,
                note=row.note,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def count_for(self, user_id: uuid.UUID) -> int:
        return int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(WishlistItemModel)
                    .where(WishlistItemModel.user_id == user_id)
                )
            ).scalar()
            or 0
        )

    async def exists(self, user_id: uuid.UUID, property_id: uuid.UUID) -> bool:
        return (
            await self._session.execute(
                select(WishlistItemModel.id).where(
                    WishlistItemModel.user_id == user_id,
                    WishlistItemModel.property_id == property_id,
                )
            )
        ).first() is not None

    async def save(
        self,
        *,
        user_id: uuid.UUID,
        property_id: uuid.UUID,
        note: str | None,
        name_snapshot: str,
    ) -> None:
        await self._session.execute(
            _UPSERT,
            {
                "user_id": user_id,
                "property_id": property_id,
                "note": note,
                "name": name_snapshot,
            },
        )

    async def remove(self, user_id: uuid.UUID, property_id: uuid.UUID) -> bool:
        result = cast(
            "CursorResult[Any]",
            await self._session.execute(
                text(
                    "DELETE FROM wishlist_items "
                    " WHERE user_id = :user_id AND property_id = :property_id"
                ),
                {"user_id": user_id, "property_id": property_id},
            ),
        )
        return bool(result.rowcount)

    async def clear(self, user_id: uuid.UUID) -> int:
        result = cast(
            "CursorResult[Any]",
            await self._session.execute(
                text("DELETE FROM wishlist_items WHERE user_id = :user_id"),
                {"user_id": user_id},
            ),
        )
        return int(result.rowcount or 0)

    async def flush(self) -> None:
        await self._session.flush()
