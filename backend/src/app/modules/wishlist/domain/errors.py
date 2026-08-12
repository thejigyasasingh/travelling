"""Wishlist errors."""

from __future__ import annotations

import uuid

from app.shared.domain.errors import BusinessRuleViolationError, DomainError


class PropertyNotSavableError(DomainError):
    """No such live listing.

    **404, not 403**, and the message does not distinguish "unpublished" from
    "never existed". Either answer would turn this endpoint into a way to
    enumerate listings a host has taken down.
    """

    code = "PROPERTY_NOT_FOUND"
    status_code = 404

    def __init__(self, property_id: uuid.UUID) -> None:
        super().__init__("Property not found.", details={"property_id": str(property_id)})


class WishlistFullError(BusinessRuleViolationError):
    """A shortlist that is no longer short.

    A cap rather than unbounded growth: past a couple of hundred this is a
    browsing history, and the list query stops fitting on a page.
    """

    code = "WISHLIST_FULL"

    def __init__(self, maximum: int) -> None:
        super().__init__(
            f"Your wishlist holds {maximum} places. Remove one to save another.",
            details={"maximum": maximum},
        )
