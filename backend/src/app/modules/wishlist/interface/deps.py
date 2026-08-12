"""Wishlist wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from app.interface.api.deps import ContainerDep
from app.modules.wishlist.application.use_cases import (
    ClearWishlist,
    ListWishlist,
    MergeWishlist,
    RemoveFromWishlist,
    SaveProperty,
)
from app.modules.wishlist.infrastructure.unit_of_work import WishlistUow


async def get_wishlist_uow(container: ContainerDep) -> AsyncIterator[WishlistUow]:
    """The primary, even for the list read.

    A guest who saves a property and immediately opens their wishlist would
    otherwise race replication and see an empty list — which reads as the save
    having failed, and produces a second save.
    """
    async with container.database.write_session() as session:
        uow = WishlistUow(session)
        yield uow
        await uow.flush()


WishlistUowDep = Annotated[WishlistUow, Depends(get_wishlist_uow)]


def list_uc(uow: WishlistUowDep) -> ListWishlist:
    return ListWishlist(items=uow.items, catalog=uow.catalog)


def save_uc(uow: WishlistUowDep) -> SaveProperty:
    return SaveProperty(items=uow.items, catalog=uow.catalog)


def remove_uc(uow: WishlistUowDep) -> RemoveFromWishlist:
    return RemoveFromWishlist(items=uow.items)


def clear_uc(uow: WishlistUowDep) -> ClearWishlist:
    return ClearWishlist(items=uow.items)


def merge_uc(uow: WishlistUowDep) -> MergeWishlist:
    return MergeWishlist(items=uow.items, catalog=uow.catalog)
