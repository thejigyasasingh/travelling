"""Saving a property, and getting the list back.

Thin on purpose. There is no domain aggregate here because there is no
invariant worth one: a wishlist is a set of ids with notes, and the only rules
are "you cannot save the same thing twice" and "you cannot save something that
does not exist", both of which are constraints the database enforces better
than Python can.

What the use cases *do* carry is the composition — reading live display data
through the property module's published contract rather than storing a copy of
it. That is the decision this module exists to make correctly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.logging import get_logger
from app.modules.property.public import PropertyCatalog
from app.modules.wishlist.application.dto import SavedProperty
from app.modules.wishlist.application.ports import WishlistRepository
from app.modules.wishlist.domain import errors

logger = get_logger(__name__)

#: A wishlist is a shortlist. Past a certain size it is a browsing history, and
#: the list query stops being one page of results.
MAX_ITEMS = 200

#: How many ids an anonymous device may hand over when signing in. Bounded
#: because the request is unauthenticated until it lands and a list of ten
#: thousand ids is a free bulk-existence oracle.
MAX_MERGE = 50


@dataclass(slots=True)
class ListWishlist:
    """The saved list, with live display data.

    Two reads and no N+1: the rows, then one batch card lookup for every
    property in them.
    """

    items: WishlistRepository
    catalog: PropertyCatalog

    async def execute(self, user_id: uuid.UUID) -> list[SavedProperty]:
        rows = await self.items.list_for(user_id)
        if not rows:
            return []

        cards = await self.catalog.cards([row.property_id for row in rows])

        saved: list[SavedProperty] = []
        for row in rows:
            card = cards.get(row.property_id)
            if card is None:
                # Hard-deleted between the read and now, or a row the FK
                # cascade has yet to clear. Dropped rather than rendered as a
                # tombstone: there is genuinely nothing left to show.
                continue
            saved.append(
                SavedProperty(
                    property_id=row.property_id,
                    # Live name when the listing is live, the tombstone when it
                    # is not — so a delisted property reads as "no longer
                    # available" under the name the guest recognises.
                    name=card.name if card.is_live else row.name_snapshot,
                    slug=card.slug,
                    city=card.city,
                    country_code=card.country_code,
                    currency=card.currency,
                    cover_image_url=card.cover_image_url,
                    # Withheld for a listing that is not on sale. A price on
                    # something nobody can book is an invitation to a support
                    # ticket.
                    from_price_minor=card.from_price_minor if card.is_live else None,
                    review_average=card.review_average,
                    review_count=card.review_count,
                    available=card.is_live,
                    note=row.note,
                    saved_at=row.created_at,
                )
            )
        return saved


@dataclass(slots=True)
class SaveProperty:
    """Add one, or update its note.

    Idempotent: saving something already saved succeeds and touches only the
    note. A heart icon is a control people press twice, and the second press
    must not be an error the UI has to explain.
    """

    items: WishlistRepository
    catalog: PropertyCatalog

    async def execute(
        self, user_id: uuid.UUID, property_id: uuid.UUID, *, note: str | None = None
    ) -> None:
        cards = await self.catalog.cards([property_id])
        card = cards.get(property_id)
        # Only live listings can be *added*. An existing save survives the
        # listing being taken down — that is the tombstone case — but saving
        # an unpublished property from a guessed id would confirm it exists.
        if card is None or not card.is_live:
            raise errors.PropertyNotSavableError(property_id)

        count = await self.items.count_for(user_id)
        if count >= MAX_ITEMS and not await self.items.exists(user_id, property_id):
            raise errors.WishlistFullError(MAX_ITEMS)

        await self.items.save(
            user_id=user_id,
            property_id=property_id,
            note=(note or "").strip()[:280] or None,
            name_snapshot=card.name,
        )


@dataclass(slots=True)
class RemoveFromWishlist:
    items: WishlistRepository

    async def execute(self, user_id: uuid.UUID, property_id: uuid.UUID) -> None:
        """Silent on a miss.

        Un-hearting something already gone is the user getting what they
        wanted. A 404 here would surface as an error toast for a no-op.
        """
        await self.items.remove(user_id, property_id)


@dataclass(slots=True)
class ClearWishlist:
    items: WishlistRepository

    async def execute(self, user_id: uuid.UUID) -> int:
        removed = await self.items.clear(user_id)
        logger.info("wishlist_cleared", user_id=str(user_id), removed=removed)
        return removed


@dataclass(slots=True)
class MergeWishlist:
    """Adopt a device's anonymous saves at sign-in.

    Without this, signing in *loses* the list a guest built while browsing —
    which is worse than the device-local behaviour it replaces, and precisely
    the moment they were most engaged.

    Additive and idempotent: it never removes anything already on the account,
    and replaying it changes nothing. Ids that are not live listings are
    skipped silently rather than failing the merge — the client's local list
    can easily contain something delisted months ago, and refusing the whole
    merge over one stale entry loses the other nineteen.
    """

    items: WishlistRepository
    catalog: PropertyCatalog

    async def execute(self, user_id: uuid.UUID, property_ids: list[uuid.UUID]) -> int:
        candidates = property_ids[:MAX_MERGE]
        if not candidates:
            return 0

        cards = await self.catalog.cards(candidates)
        room = MAX_ITEMS - await self.items.count_for(user_id)

        merged = 0
        for property_id in candidates:
            if room <= 0:
                break
            card = cards.get(property_id)
            if card is None or not card.is_live:
                continue
            if await self.items.exists(user_id, property_id):
                continue
            await self.items.save(
                user_id=user_id, property_id=property_id, note=None, name_snapshot=card.name
            )
            merged += 1
            room -= 1

        logger.info("wishlist_merged", user_id=str(user_id), offered=len(candidates), merged=merged)
        return merged
