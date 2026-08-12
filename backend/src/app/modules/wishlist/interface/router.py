"""Wishlist endpoints.

Every route is scoped to the authenticated user by the use case, not by a
parameter. There is no `user_id` in any path here and there must never be one:
a wishlist is a list of places someone is thinking about going, which is more
revealing than most of what this platform stores.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.logging import get_logger
from app.core.serialization import dto_dict
from app.interface.api.deps import ActorDep
from app.modules.wishlist.application.use_cases import (
    ClearWishlist,
    ListWishlist,
    MergeWishlist,
    RemoveFromWishlist,
    SaveProperty,
)
from app.modules.wishlist.interface import deps
from app.modules.wishlist.interface.schemas import (
    MergeRequest,
    MergeResponse,
    SavedPropertyResponse,
    SaveRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("", response_model=list[SavedPropertyResponse], summary="Your saved places")
async def list_wishlist(
    actor: ActorDep, use_case: Annotated[ListWishlist, Depends(deps.list_uc)]
) -> list[SavedPropertyResponse]:
    """Prices and ratings are read live on every request.

    Two queries regardless of list length — the rows, then one batch card
    lookup — rather than one per saved property.
    """
    saved = await use_case.execute(actor.user_id)  # type: ignore[arg-type]
    return [SavedPropertyResponse(**dto_dict(item)) for item in saved]


@router.put(
    "/{property_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Save a place",
)
async def save(
    property_id: uuid.UUID,
    body: SaveRequest,
    actor: ActorDep,
    uow: deps.WishlistUowDep,
    use_case: Annotated[SaveProperty, Depends(deps.save_uc)],
) -> None:
    """PUT, not POST, because saving is idempotent.

    A heart icon is a control people press twice on a slow connection, and the
    second press has to be a no-op rather than a duplicate or a 409.
    """
    await use_case.execute(actor.user_id, property_id, note=body.note)  # type: ignore[arg-type]
    await uow.commit()


@router.delete(
    "/{property_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a place",
)
async def remove(
    property_id: uuid.UUID,
    actor: ActorDep,
    uow: deps.WishlistUowDep,
    use_case: Annotated[RemoveFromWishlist, Depends(deps.remove_uc)],
) -> None:
    """204 whether or not it was there.

    Un-hearting something already gone is the guest getting what they asked
    for; a 404 would surface as an error toast for a successful no-op.
    """
    await use_case.execute(actor.user_id, property_id)  # type: ignore[arg-type]
    await uow.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Clear your wishlist")
async def clear(
    actor: ActorDep,
    uow: deps.WishlistUowDep,
    use_case: Annotated[ClearWishlist, Depends(deps.clear_uc)],
) -> None:
    await use_case.execute(actor.user_id)  # type: ignore[arg-type]
    await uow.commit()


@router.post("/merge", response_model=MergeResponse, summary="Adopt this device's saves")
async def merge(
    body: MergeRequest,
    actor: ActorDep,
    uow: deps.WishlistUowDep,
    use_case: Annotated[MergeWishlist, Depends(deps.merge_uc)],
) -> MergeResponse:
    """Called once, after signing in.

    Without it, signing in loses the list a guest built while browsing signed
    out — worse than the device-local behaviour it replaces, and at the moment
    they were most engaged.

    Additive and idempotent: nothing already saved is removed, ids that are no
    longer live are skipped rather than failing the whole merge.
    """
    merged = await use_case.execute(actor.user_id, body.property_ids)  # type: ignore[arg-type]
    await uow.commit()
    return MergeResponse(merged=merged)
