"""The property module's **published contract**.

Other modules import from here and from nowhere else inside
``app.modules.property`` — enforced by a contract in ``.importlinter``.

Why this exists at all. In a modular monolith every module can physically
import every other, so the boundary has to be a decision rather than an
accident. Without one, booking would import ``property.domain.entities``,
depend on the shape of that aggregate, and the property module could no longer
change its internals without breaking bookings. Extracting either into its own
service would then be a rewrite rather than a deployment change.

What crosses the boundary is deliberately narrow and *flat*:

* :class:`PropertySnapshot` / :class:`RoomSnapshot` — read models, not
  aggregates. Booking gets the facts it needs to price and validate a stay,
  and no behaviour it could accidentally invoke.
* :class:`InventoryService` — the only way to take or release inventory. The
  SQL that mutates ``room_inventory`` stays in the module that owns the table,
  which keeps the overbooking guarantee in one auditable place.
* :func:`price_stay` — pricing, re-exported so booking computes the same
  numbers the guest was quoted, from the same code.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.property.public.contract import (
    HoldResult,
    InventoryService,
    PropertyCard,
    PropertyCatalog,
    PropertySnapshot,
    RatingWriter,
    RoomSnapshot,
    price_stay,
)


def build_property_catalog(session: AsyncSession) -> PropertyCatalog:
    """Construct the read adapter. Callers pass their own session, so the
    reads happen inside their transaction."""
    from app.modules.property.public.adapters import SqlPropertyCatalog

    return SqlPropertyCatalog(session)


def build_inventory_service(session: AsyncSession) -> InventoryService:
    """Construct the inventory adapter.

    A factory rather than an exported class: consumers name the *contract*, and
    the concrete adapter — with its dependency on this module's tables — stays
    an implementation detail behind the boundary.
    """
    from app.modules.property.public.adapters import SqlInventoryService

    return SqlInventoryService(session)


__all__ = [
    "HoldResult",
    "InventoryService",
    "PropertyCard",
    "PropertyCatalog",
    "PropertySnapshot",
    "RatingWriter",
    "RoomSnapshot",
    "build_inventory_service",
    "build_property_catalog",
    "build_rating_writer",
    "price_stay",
]


def build_rating_writer(session: AsyncSession) -> RatingWriter:
    """Construct the rating writer against the caller's session, so a review and
    the property rating it moves commit in one transaction."""
    from app.modules.property.public.adapters import SqlRatingWriter

    return SqlRatingWriter(session)
