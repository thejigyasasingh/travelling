"""Payment request/response schemas.

Amounts are **integer minor units** everywhere on the wire — paise, not rupees.
A float amount is a rounding bug waiting for the first ₹0.005, and Razorpay's
own API is minor-unit for the same reason.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateOrderRequest(BaseModel):
    booking_id: uuid.UUID

    #: Deliberately *only* the booking id. The amount comes from the booking,
    #: never from the client — a client-supplied amount is how a ₹40,000 stay
    #: gets paid for with ₹1.


class VerifyCheckoutRequest(BaseModel):
    """The three fields Razorpay Checkout hands back to the browser.

    All attacker-controlled. The signature is what makes the other two
    trustworthy, and it is verified server-side against a secret the browser
    never sees.
    """

    razorpay_order_id: str = Field(max_length=64)
    razorpay_payment_id: str = Field(max_length=64)
    razorpay_signature: str = Field(max_length=128)


class RefundRequest(BaseModel):
    amount_minor: int | None = Field(
        default=None,
        gt=0,
        description="Omit to refund everything still refundable.",
    )
    reason: str = Field(default="requested_by_customer", max_length=100)
    speed: str = Field(
        default="normal",
        pattern="^(normal|optimum)$",
        description="`optimum` costs more and settles in minutes; `normal` is free "
        "and settles in 5-7 working days.",
    )


class CheckoutSessionResponse(BaseModel):
    payment_id: uuid.UUID
    gateway_order_id: str
    #: The **public** merchant key. Identifies the account, authorises nothing.
    key_id: str
    amount_minor: int
    currency: str
    booking_reference: str
    prefill_name: str
    prefill_email: str
    prefill_contact: str
    property_name: str
    #: Seconds until the booking's hold lapses. Drives the checkout countdown.
    expires_in: int | None = None
    attempt_number: int = 1
    notes: dict[str, str] = Field(default_factory=dict)


class PaymentResultResponse(BaseModel):
    payment_id: uuid.UUID
    status: str
    booking_id: uuid.UUID
    booking_reference: str
    amount_minor: int
    currency: str
    method: str
    invoice_number: str | None = None
    booking_status: str | None = None
    gateway_payment_id: str | None = None


class LedgerEntryResponse(BaseModel):
    kind: str
    amount_minor: int
    currency: str
    #: Positive in, negative out. Summing this column over a payment gives
    #: exactly what the platform holds.
    signed_minor: int
    occurred_at: datetime
    gateway_reference: str | None = None
    note: str | None = None


class RefundResponse(BaseModel):
    id: uuid.UUID
    status: str
    amount_minor: int
    currency: str
    reason: str
    speed: str
    gateway_refund_id: str | None = None
    requested_at: datetime
    completed_at: datetime | None = None
    failure_reason: str | None = None


class PaymentResponse(BaseModel):
    id: uuid.UUID
    status: str
    booking_id: uuid.UUID
    booking_reference: str
    amount_minor: int
    currency: str
    method: str
    #: Card last-4 or UPI VPA — never a full card number, which never reaches
    #: this system.
    instrument: str | None = None
    gateway_order_id: str
    gateway_payment_id: str | None = None
    attempt_number: int
    created_at: datetime | None = None
    authorized_at: datetime | None = None
    captured_at: datetime | None = None
    failure_code: str | None = None
    failure_reason: str | None = None
    refunded_minor: int
    refundable_minor: int
    net_minor: int
    refunds: list[RefundResponse] = Field(default_factory=list)
    ledger: list[LedgerEntryResponse] = Field(default_factory=list)


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    next_cursor: str | None = None


class WebhookAck(BaseModel):
    """Razorpay reads only the status code; this exists so the body is
    diagnosable when someone replays a delivery by hand."""

    status: str
