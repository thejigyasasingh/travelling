"""Booking DTOs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class CreateBookingInput:
    property_id: uuid.UUID
    room_type_id: uuid.UUID
    check_in: date
    check_out: date
    adults: int = 1
    children: int = 0
    infants: int = 0
    rooms: int = 1
    guest_name: str = ""
    guest_email: str = ""
    guest_phone: str = ""
    special_requests: str | None = None
    #: What the guest was shown. The server re-prices and refuses if it moved —
    #: see `PriceChangedError` for why silent repricing is not an option.
    quoted_total_minor: int | None = None
    source: str = "web"


@dataclass(frozen=True, slots=True)
class ConfirmBookingInput:
    booking_id: uuid.UUID
    payment_id: str
    #: The gateway's amount, cross-checked against the booking. A mismatch
    #: means either a tampered client or a bug, and both must stop the
    #: confirmation rather than be reconciled later.
    paid_amount_minor: int | None = None


@dataclass(frozen=True, slots=True)
class CancelBookingInput:
    booking_id: uuid.UUID
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class NightlyRateView:
    date: date
    amount_minor: int
    source: str


@dataclass(frozen=True, slots=True)
class RefundView:
    status: str
    amount_minor: int
    currency: str
    reason: str
    requested_at: datetime | None = None
    completed_at: datetime | None = None
    gateway_refund_id: str | None = None


@dataclass(frozen=True, slots=True)
class BookingView:
    id: uuid.UUID
    reference: str
    status: str
    property_id: uuid.UUID
    property_name: str
    room_type_id: uuid.UUID
    room_type_name: str
    check_in: date
    check_out: date
    nights: int
    adults: int
    children: int
    infants: int
    rooms: int
    guest_name: str
    guest_email: str
    guest_phone: str
    special_requests: str | None
    accommodation_minor: int
    extra_guest_minor: int
    cleaning_fee_minor: int
    tax_minor: int
    platform_fee_minor: int
    total_minor: int
    currency: str
    cancellation_policy: str
    created_at: datetime | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    cancelled_by: str | None
    cancellation_reason: str | None
    invoice_number: str | None
    #: Seconds left on the hold. Drives the checkout countdown; ``None`` once
    #: the booking is no longer time-limited.
    hold_expires_in: int | None = None
    nightly_rates: list[NightlyRateView] = field(default_factory=list)
    refund: RefundView | None = None
    #: Withheld until the booking is confirmed — the exact address is what a
    #: guest needs on arrival and what nobody else should have.
    property_address: str | None = None
    #: What cancelling right now would return. Guest view only.
    refund_preview: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class BookingListView:
    items: list[BookingView]
    next_cursor: str | None = None
    total: int | None = None


@dataclass(frozen=True, slots=True)
class InvoiceView:
    number: str
    issued_at: datetime
    financial_year: str
    booking_reference: str
    supplier_name: str
    supplier_address: str
    supplier_gstin: str | None
    guest_name: str
    guest_email: str
    property_name: str
    check_in: date
    check_out: date
    nights: int
    rooms: int
    lines: list[dict[str, Any]]
    subtotal_minor: int
    cgst_minor: int
    sgst_minor: int
    igst_minor: int
    tax_total_minor: int
    total_minor: int
    total_in_words: str
    place_of_supply: str
    currency: str
