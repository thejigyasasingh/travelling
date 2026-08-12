"""HTTP schemas for the booking module."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

BookingStatusLiteral = Literal[
    "pending_payment",
    "pending_approval",
    "confirmed",
    "in_stay",
    "completed",
    "cancelled",
    "expired",
    "rejected",
    "no_show",
]

MoneyMinor = Annotated[int, Field(ge=0, le=100_000_000_00)]


class CreateBookingRequest(BaseModel):
    property_id: uuid.UUID
    room_type_id: uuid.UUID
    check_in: date
    check_out: date
    adults: int = Field(default=1, ge=1, le=30)
    children: int = Field(default=0, ge=0, le=30)
    infants: int = Field(default=0, ge=0, le=30)
    rooms: int = Field(default=1, ge=1, le=8)
    guest_name: str = Field(min_length=2, max_length=150)
    guest_email: EmailStr
    guest_phone: str = Field(min_length=6, max_length=20)
    special_requests: str | None = Field(default=None, max_length=1000)
    quoted_total_minor: MoneyMinor | None = Field(
        default=None,
        description=(
            "The total the guest was shown. The server re-prices and returns 409 "
            "BOOKING_PRICE_CHANGED if it moved — it never silently charges a "
            "different amount."
        ),
    )
    source: Literal["web", "ios", "android", "partner"] = "web"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "property_id": "0192f4c1-0000-7000-8000-000000000001",
                "room_type_id": "0192f4c1-0000-7000-8000-000000000002",
                "check_in": "2026-09-14",
                "check_out": "2026-09-17",
                "adults": 2,
                "guest_name": "Priya Sharma",
                "guest_email": "priya@example.com",
                "guest_phone": "+919876543210",
                "quoted_total_minor": 2856000,
            }
        }
    )

    @model_validator(mode="after")
    def _dates_are_ordered(self) -> CreateBookingRequest:
        if self.check_out <= self.check_in:
            msg = "check_out must be after check_in"
            raise ValueError(msg)
        if (self.check_out - self.check_in).days > 90:
            msg = "A stay may not exceed 90 nights"
            raise ValueError(msg)
        return self


class CancelBookingRequest(BaseModel):
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Shown to the vendor. Optional for a guest, expected from staff.",
    )


class RejectBookingRequest(BaseModel):
    reason: str = Field(
        min_length=5,
        max_length=500,
        description="Required. A rejection the guest cannot understand becomes a support ticket.",
    )


class ConfirmBookingRequest(BaseModel):
    """Called by the payment webhook, not by a browser.

    A client-reported "I paid" is a claim; the gateway's signed callback is
    evidence.
    """

    payment_id: str = Field(min_length=4, max_length=100)
    paid_amount_minor: MoneyMinor | None = Field(
        default=None, description="Cross-checked against the booking total."
    )


# ══════════════════════════════════════════════════════════════════════════
# Responses
# ══════════════════════════════════════════════════════════════════════════


class NightlyRateResponse(BaseModel):
    date: date
    amount_minor: int
    source: Literal["override", "weekend", "base"]


class RefundResponse(BaseModel):
    status: Literal["not_applicable", "pending", "processing", "completed", "failed"]
    amount_minor: int
    currency: str
    reason: str
    requested_at: datetime | None = None
    completed_at: datetime | None = None
    gateway_refund_id: str | None = None


class BookingResponse(BaseModel):
    id: uuid.UUID
    reference: str = Field(description="Quote this to support. e.g. RW-26-K7M3QP2X")
    status: BookingStatusLiteral
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
    hold_expires_in: int | None = Field(
        default=None,
        description="Seconds left to pay. Drives the checkout countdown; null once confirmed.",
    )
    nightly_rates: list[NightlyRateResponse] = Field(default_factory=list)
    refund: RefundResponse | None = None
    property_address: str | None = Field(
        default=None, description="Released only once the booking is confirmed."
    )
    refund_preview: dict[str, Any] | None = Field(
        default=None, description="What cancelling right now would return."
    )


class BookingListResponse(BaseModel):
    items: list[BookingResponse]
    next_cursor: str | None = None
    total: int | None = None


class RefundPreviewResponse(BaseModel):
    """Shown before the cancel button, never after.

    A guest who cancels and only then learns the amount opens a ticket; one who
    sees it first mostly does not.
    """

    policy: str
    hours_before_check_in: float
    applied_percent: str
    accommodation_minor: int
    extra_guest_minor: int
    cleaning_fee_minor: int
    tax_minor: int
    platform_fee_minor: int
    total_minor: int
    vendor_retains_minor: int
    reason: str
    currency: str
    cancellable: bool
    policy_tiers: list[dict[str, Any]]


class InvoiceLineResponse(BaseModel):
    description: str
    hsn_code: str
    quantity: int
    unit_amount_minor: int
    amount_minor: int
    tax_rate: str


class InvoiceResponse(BaseModel):
    number: str
    issued_at: datetime
    financial_year: str = Field(description="India's FY runs April to March, e.g. 2026-27.")
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
    lines: list[InvoiceLineResponse]
    subtotal_minor: int
    cgst_minor: int
    sgst_minor: int
    igst_minor: int
    tax_total_minor: int
    total_minor: int
    total_in_words: str
    place_of_supply: str
    currency: str
