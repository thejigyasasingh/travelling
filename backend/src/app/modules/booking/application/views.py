"""Booking → view mapping.

One place, because "who may see the exact address" and "who may see the guest's
phone number" have to hold identically on the detail page, in the history list
and in the vendor's arrivals view.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.modules.booking.application.dto import (
    BookingView,
    NightlyRateView,
    RefundView,
)
from app.modules.booking.domain.entities import Booking


def to_booking_view(
    booking: Booking,
    *,
    now: datetime,
    include_address: bool = False,
    property_address: str | None = None,
    refund_preview: dict[str, object] | None = None,
) -> BookingView:
    """Map for the wire.

    ``include_address`` is true only once the booking is confirmed. Before
    that the guest has not committed, and handing out the exact address of an
    occupied private home to anyone who starts a checkout is how a listing
    gets scraped or a host gets doorstepped.
    """
    charges = booking.charges

    return BookingView(
        id=booking.id,
        reference=str(booking.reference),
        status=booking.status.value,
        property_id=booking.property_id,
        property_name=booking.property_name,
        room_type_id=booking.room_type_id,
        room_type_name=booking.room_type_name,
        check_in=booking.stay.check_in_date,
        check_out=booking.stay.check_out_date,
        nights=booking.stay.nights,
        adults=booking.adults,
        children=booking.children,
        infants=booking.infants,
        rooms=booking.rooms,
        guest_name=booking.guest.full_name,
        guest_email=booking.guest.email,
        guest_phone=booking.guest.phone,
        special_requests=booking.guest.special_requests,
        accommodation_minor=charges.accommodation.amount_minor,
        extra_guest_minor=charges.extra_guest.amount_minor,
        cleaning_fee_minor=charges.cleaning_fee.amount_minor,
        tax_minor=charges.tax.amount_minor,
        platform_fee_minor=charges.platform_fee.amount_minor,
        total_minor=charges.total.amount_minor,
        currency=charges.currency,
        cancellation_policy=booking.cancellation_policy.value,
        created_at=booking.created_at,
        confirmed_at=booking.confirmed_at,
        cancelled_at=booking.cancelled_at,
        cancelled_by=booking.cancelled_by.value if booking.cancelled_by else None,
        cancellation_reason=booking.cancellation_reason,
        invoice_number=booking.invoice_number,
        # Drives the checkout countdown. None once the booking is no longer
        # time-limited, so the client knows to stop the timer rather than
        # showing 00:00 forever.
        hold_expires_in=(booking.hold.seconds_remaining(now) if booking.hold is not None else None),
        nightly_rates=[_nightly_view(n) for n in booking.nightly_rates],
        refund=_refund_view(booking),
        property_address=property_address if include_address else None,
        refund_preview=refund_preview,
    )


def _refund_view(booking: Booking) -> RefundView | None:
    refund = booking.refund
    if refund is None:
        return None
    return RefundView(
        status=refund.status.value,
        amount_minor=refund.amount.amount_minor,
        currency=refund.amount.currency,
        reason=refund.reason,
        requested_at=refund.requested_at,
        completed_at=refund.completed_at,
        gateway_refund_id=refund.gateway_refund_id,
    )


def _nightly_view(raw: dict[str, Any]) -> NightlyRateView:
    """The per-night breakdown round-trips through JSONB, so dates arrive as
    ISO strings on the way back and as `date` objects when freshly quoted."""
    value = raw["date"]
    stay_date = value if isinstance(value, date) else date.fromisoformat(str(value))
    return NightlyRateView(
        date=stay_date,
        amount_minor=int(str(raw["amount_minor"])),
        source=str(raw["source"]),
    )
