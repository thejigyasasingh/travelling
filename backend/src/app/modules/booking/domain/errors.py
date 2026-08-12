"""Booking domain errors."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.shared.domain.errors import BusinessRuleViolationError, DomainError


class DatesUnavailableError(BusinessRuleViolationError):
    """The nights are taken.

    Carries the blocking dates so the UI can offer adjacent ones. A bare
    "unavailable" leaves the guest with nowhere to go, and that is where most
    abandoned bookings actually happen.
    """

    code = "BOOKING_DATES_UNAVAILABLE"

    def __init__(self, unavailable: list[date] | None = None) -> None:
        super().__init__(
            "Those dates are no longer available.",
            details={"unavailable_dates": [d.isoformat() for d in (unavailable or [])]},
        )


class PriceChangedError(BusinessRuleViolationError):
    """The price moved between the quote and the booking attempt.

    The booking is **refused**, not silently repriced. Charging a different
    amount from the one the guest agreed to is a chargeback and, in most
    jurisdictions, illegal. The new price is returned so the client can show
    it and ask again.
    """

    code = "BOOKING_PRICE_CHANGED"

    def __init__(self, quoted_minor: int, current_minor: int, currency: str) -> None:
        super().__init__(
            "The price for these dates has changed. Please review and try again.",
            details={
                "quoted_minor": quoted_minor,
                "current_minor": current_minor,
                "difference_minor": current_minor - quoted_minor,
                "currency": currency,
            },
        )


class PropertyNotBookableError(BusinessRuleViolationError):
    """Unpublished, suspended, or with no room types.

    Reachable through a stale link, a bookmark, or a search result cached
    before the vendor withdrew the listing.
    """

    code = "PROPERTY_NOT_BOOKABLE"

    def __init__(self, reason: str = "unavailable") -> None:
        super().__init__("This property is not accepting bookings.", details={"reason": reason})


class InvalidStayError(BusinessRuleViolationError):
    code = "INVALID_STAY"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message, details=details)


class OccupancyExceededError(BusinessRuleViolationError):
    code = "OCCUPANCY_EXCEEDED"

    def __init__(self, requested: int, maximum: int) -> None:
        super().__init__(
            f"This room accommodates at most {maximum} guests.",
            details={"requested": requested, "maximum": maximum},
        )


class InvalidBookingTransitionError(BusinessRuleViolationError):
    """Every status change is checked against an explicit table.

    Modelled rather than allowed-by-default because the illegal moves are the
    dangerous ones: confirming an expired hold whose inventory has already been
    released would create a booking with no room behind it.
    """

    code = "INVALID_BOOKING_TRANSITION"

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            f"A {current.replace('_', ' ')} booking cannot become {target.replace('_', ' ')}.",
            details={"current": current, "target": target},
        )


class BookingNotCancellableError(BusinessRuleViolationError):
    code = "BOOKING_NOT_CANCELLABLE"

    def __init__(self, status: str) -> None:
        super().__init__("This booking can no longer be cancelled.", details={"status": status})


class HoldExpiredError(BusinessRuleViolationError):
    """Payment arrived after the hold lapsed.

    A real race, not a theoretical one: a guest completes 3-D Secure at minute
    16 and the gateway calls back. The inventory is already released and may
    have been resold, so the payment is refunded rather than the booking being
    resurrected.
    """

    code = "BOOKING_HOLD_EXPIRED"

    def __init__(self) -> None:
        super().__init__(
            "Your reservation hold expired before payment completed. "
            "Any amount charged will be refunded automatically."
        )


class BookingAccessDeniedError(DomainError):
    """Not this guest's booking, and not their vendor's.

    Surfaces as 404 rather than 403 — confirming that a reference exists turns
    the booking-lookup endpoint into an oracle for guessing references.
    """

    code = "BOOKING_NOT_FOUND"
    #: 404, not 403 — a 403 confirms the reference exists and turns the lookup
    #: endpoint into an oracle for guessing booking references.
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Booking not found.")


class RefundAlreadyIssuedError(BusinessRuleViolationError):
    """Refunding twice is real money leaving twice.

    Guarded in the domain *and* by a unique constraint, because a retried
    webhook and an impatient support agent can arrive at the same moment.
    """

    code = "REFUND_ALREADY_ISSUED"

    def __init__(self) -> None:
        super().__init__("A refund has already been issued for this booking.")


class RefundExceedsPaymentError(BusinessRuleViolationError):
    code = "REFUND_EXCEEDS_PAYMENT"

    def __init__(self, refund_minor: int, paid_minor: int) -> None:
        super().__init__(
            "A refund cannot exceed the amount paid.",
            details={"refund_minor": refund_minor, "paid_minor": paid_minor},
        )


class InvoiceAlreadyIssuedError(BusinessRuleViolationError):
    """Invoices are immutable once numbered.

    Tax invoices must be sequential and unaltered; a correction is a credit
    note referencing the original, never an edit to it.
    """

    code = "INVOICE_ALREADY_ISSUED"

    def __init__(self, number: str) -> None:
        super().__init__(
            "An invoice has already been issued for this booking.",
            details={"invoice_number": number},
        )


class InvoiceNotAvailableError(BusinessRuleViolationError):
    code = "INVOICE_NOT_AVAILABLE"

    def __init__(self, status: str) -> None:
        super().__init__(
            "An invoice is issued once the booking is confirmed.",
            details={"status": status},
        )
