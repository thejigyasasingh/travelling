"""Payment DTOs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class CreateOrderInput:
    booking_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    """Everything the client needs to open Razorpay Checkout.

    ``key_id`` is public — it identifies the merchant and authorises nothing.
    The secret never leaves the server, which is why signature verification
    happens here rather than in the browser.
    """

    payment_id: uuid.UUID
    gateway_order_id: str
    key_id: str
    amount_minor: int
    currency: str
    booking_reference: str
    #: Prefills the checkout form. Fewer fields to retype is measurably fewer
    #: abandoned payments.
    prefill_name: str
    prefill_email: str
    prefill_contact: str
    property_name: str
    #: Seconds the guest has left before the booking's hold lapses. The client
    #: shows a countdown; a checkout that silently expires is a support ticket.
    expires_in: int | None = None
    attempt_number: int = 1
    notes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VerifyCheckoutInput:
    """What the browser posts back after Razorpay Checkout succeeds.

    All three fields are attacker-controlled. The signature is what makes them
    trustworthy — see ``domain/signature.py``.
    """

    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@dataclass(frozen=True, slots=True)
class PaymentResult:
    payment_id: uuid.UUID
    status: str
    booking_id: uuid.UUID
    booking_reference: str
    amount_minor: int
    currency: str
    method: str
    #: Populated once the booking is confirmed, so the client can go straight
    #: to a confirmation screen with an invoice rather than polling.
    invoice_number: str | None = None
    booking_status: str | None = None
    gateway_payment_id: str | None = None


@dataclass(frozen=True, slots=True)
class RefundInput:
    payment_id: uuid.UUID
    amount_minor: int | None = None  # None = full remaining refundable
    reason: str = "requested_by_customer"
    speed: str = "normal"


@dataclass(frozen=True, slots=True)
class LedgerEntryView:
    kind: str
    amount_minor: int
    currency: str
    signed_minor: int
    occurred_at: datetime
    gateway_reference: str | None
    note: str | None


@dataclass(frozen=True, slots=True)
class RefundView:
    id: uuid.UUID
    status: str
    amount_minor: int
    currency: str
    reason: str
    speed: str
    gateway_refund_id: str | None
    requested_at: datetime
    completed_at: datetime | None
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class PaymentView:
    id: uuid.UUID
    status: str
    booking_id: uuid.UUID
    booking_reference: str
    amount_minor: int
    currency: str
    method: str
    #: Card last-4 or UPI VPA. Enough for a guest to recognise which
    #: instrument was used; never the full number, which we never receive.
    instrument: str | None
    gateway_order_id: str
    gateway_payment_id: str | None
    attempt_number: int
    created_at: datetime | None
    authorized_at: datetime | None
    captured_at: datetime | None
    failure_code: str | None
    failure_reason: str | None
    refunded_minor: int
    refundable_minor: int
    #: `sum(ledger)` — what the platform actually holds after fees and refunds.
    net_minor: int
    refunds: list[RefundView] = field(default_factory=list)
    ledger: list[LedgerEntryView] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PaymentListView:
    items: list[PaymentView]
    next_cursor: str | None = None


@dataclass(frozen=True, slots=True)
class WebhookInput:
    """A raw webhook delivery.

    ``raw_body`` is the **exact bytes** Razorpay sent. Re-serialised JSON
    produces a different HMAC and the signature will not match — see
    ``domain/signature.py``.
    """

    raw_body: bytes
    signature: str
    event_id: str
    payload: dict[str, Any]
