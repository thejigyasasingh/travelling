"""Property domain errors."""

from __future__ import annotations

from typing import Any

from app.shared.domain.errors import BusinessRuleViolationError, DomainError


class PropertyNotPublishableError(BusinessRuleViolationError):
    """The listing is incomplete.

    Carries **every** missing requirement at once. A vendor fixing one thing,
    resubmitting, and being told about the next is how listings get abandoned
    half-finished — and an abandoned listing is inventory we never sell.
    """

    code = "PROPERTY_NOT_PUBLISHABLE"

    def __init__(self, missing: list[str]) -> None:
        super().__init__(
            "This listing is not ready to publish.",
            details={"missing": missing, "count": len(missing)},
        )
        self.missing = missing


class InvalidStatusTransitionError(BusinessRuleViolationError):
    """Not every status change is legal.

    Modelled explicitly rather than allowing any status to be set, because a
    vendor being able to move their own listing from `suspended` back to
    `published` would make suspension meaningless.
    """

    code = "INVALID_STATUS_TRANSITION"

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            f"A {current} listing cannot become {target}.",
            details={"current": current, "target": target},
        )


class PropertyNotEditableError(BusinessRuleViolationError):
    code = "PROPERTY_NOT_EDITABLE"

    def __init__(self, status: str) -> None:
        super().__init__(
            "This listing cannot be edited in its current state.",
            details={"status": status},
        )


class VendorScopeError(DomainError):
    """The caller is a vendor, but not *this* property's vendor.

    Deliberately a 404 at the interface layer, not a 403: confirming that a
    property id exists lets a competitor enumerate our inventory and learn
    which vendors own what.
    """

    code = "PROPERTY_NOT_FOUND"

    def __init__(self) -> None:
        super().__init__("Property not found.")


class DuplicateRoomTypeError(BusinessRuleViolationError):
    code = "DUPLICATE_ROOM_TYPE"

    def __init__(self, name: str) -> None:
        super().__init__(
            f"This property already has a room type called {name!r}.",
            details={"name": name},
        )


class RoomTypeNotFoundError(DomainError):
    code = "ROOM_TYPE_NOT_FOUND"

    def __init__(self, identifier: Any = None) -> None:
        super().__init__(
            "Room type not found.", details={"room_type_id": str(identifier)} if identifier else {}
        )


class LastRoomTypeError(BusinessRuleViolationError):
    """A published listing with no rooms is unbookable and, to a searching
    guest, indistinguishable from a broken page."""

    code = "LAST_ROOM_TYPE"

    def __init__(self) -> None:
        super().__init__(
            "A published listing must keep at least one room type. Unpublish the listing first."
        )


class WholeUnitRoomLimitError(BusinessRuleViolationError):
    """A villa or apartment is one bookable unit by definition.

    Letting one carry three room types would make "how many are available?"
    ambiguous for the whole class of property.
    """

    code = "WHOLE_UNIT_ROOM_LIMIT"

    def __init__(self, property_type: str) -> None:
        super().__init__(
            f"A {property_type} is booked as a whole unit and can have only one room type.",
            details={"property_type": property_type},
        )


class ImageLimitError(BusinessRuleViolationError):
    code = "IMAGE_LIMIT_REACHED"

    def __init__(self, limit: int) -> None:
        super().__init__(f"A listing may have at most {limit} images.", details={"limit": limit})


class ImageNotFoundError(DomainError):
    code = "IMAGE_NOT_FOUND"

    def __init__(self) -> None:
        super().__init__("Image not found on this listing.")


class CoverImageRequiredError(BusinessRuleViolationError):
    """The cover image is what a guest sees in search. A listing without one
    renders as a grey box and is effectively invisible."""

    code = "COVER_IMAGE_REQUIRED"

    def __init__(self) -> None:
        super().__init__("A listing must keep a cover image. Set another one first.")


class UnknownAmenityError(BusinessRuleViolationError):
    """Amenities come from a catalogue.

    Free text would mean "Wi-Fi", "wifi", "WiFi" and "Wireless Internet" as
    four distinct filters, none of which matches what a guest actually clicks.
    """

    code = "UNKNOWN_AMENITY"

    def __init__(self, codes: list[str]) -> None:
        super().__init__(
            "One or more amenities are not recognised.", details={"unknown": sorted(codes)}
        )


class SearchWindowError(BusinessRuleViolationError):
    """Search dates that no query can usefully answer."""

    code = "INVALID_SEARCH_WINDOW"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message, details=details)
