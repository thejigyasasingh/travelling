"""Payment domain events.

``PaymentCaptured`` is the one that matters: it is what tells the booking module
money actually moved. Note that ``PaymentAuthorized`` deliberately does **not**
confirm a booking — authorised funds are reserved, not taken, and an
authorisation that is never captured silently reverses.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

from app.shared.domain.events import DomainEvent

AGGREGATE = "payment"


@dataclass(frozen=True, kw_only=True)
class PaymentOrderCreated(DomainEvent):
    event_type: ClassVar[str] = "payment.order.created"
    aggregate_type: ClassVar[str] = AGGREGATE

    booking_id: uuid.UUID
    booking_reference: str
    gateway_order_id: str
    amount_minor: int
    currency: str
    attempt_number: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "payment_id": str(self.aggregate_id),
            "booking_id": str(self.booking_id),
            "booking_reference": self.booking_reference,
            "gateway_order_id": self.gateway_order_id,
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "attempt_number": self.attempt_number,
        }


@dataclass(frozen=True, kw_only=True)
class PaymentAuthorized(DomainEvent):
    """Funds reserved, not taken.

    Consumed by the capture job, which has a narrow window: an authorisation
    left uncaptured reverses after a few days and the platform is holding a
    confirmed booking with no money behind it.
    """

    event_type: ClassVar[str] = "payment.authorized"
    aggregate_type: ClassVar[str] = AGGREGATE

    booking_id: uuid.UUID
    gateway_payment_id: str
    amount_minor: int
    currency: str
    method: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "payment_id": str(self.aggregate_id),
            "booking_id": str(self.booking_id),
            "gateway_payment_id": self.gateway_payment_id,
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "method": self.method,
        }


@dataclass(frozen=True, kw_only=True)
class PaymentCaptured(DomainEvent):
    """Money has moved. The booking may be confirmed.

    Consumers: booking (confirm), notification (receipt), analytics, and the
    finance reconciliation job.
    """

    event_type: ClassVar[str] = "payment.captured"
    aggregate_type: ClassVar[str] = AGGREGATE

    booking_id: uuid.UUID
    booking_reference: str
    guest_id: uuid.UUID
    gateway_payment_id: str
    amount_minor: int
    currency: str
    method: str
    fee_minor: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "payment_id": str(self.aggregate_id),
            "booking_id": str(self.booking_id),
            "booking_reference": self.booking_reference,
            "guest_id": str(self.guest_id),
            "gateway_payment_id": self.gateway_payment_id,
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "method": self.method,
            "fee_minor": self.fee_minor,
        }


@dataclass(frozen=True, kw_only=True)
class PaymentFailed(DomainEvent):
    """The bank declined, or the customer abandoned the flow.

    Carries the attempt number so the notification consumer can escalate — a
    third failure means the guest needs a different method, not another
    "please try again" email.
    """

    event_type: ClassVar[str] = "payment.failed"
    aggregate_type: ClassVar[str] = AGGREGATE

    booking_id: uuid.UUID
    booking_reference: str
    guest_id: uuid.UUID
    gateway_payment_id: str | None
    code: str | None
    reason: str | None
    attempt_number: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "payment_id": str(self.aggregate_id),
            "booking_id": str(self.booking_id),
            "booking_reference": self.booking_reference,
            "guest_id": str(self.guest_id),
            "gateway_payment_id": self.gateway_payment_id,
            "code": self.code,
            "reason": self.reason,
            "attempt_number": self.attempt_number,
        }


@dataclass(frozen=True, kw_only=True)
class RefundRecorded(DomainEvent):
    """A refund is intended. Drives the worker that calls the gateway."""

    event_type: ClassVar[str] = "payment.refund.recorded"
    aggregate_type: ClassVar[str] = AGGREGATE

    booking_id: uuid.UUID
    refund_id: uuid.UUID
    amount_minor: int
    currency: str
    reason: str
    idempotency_key: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "payment_id": str(self.aggregate_id),
            "booking_id": str(self.booking_id),
            "refund_id": str(self.refund_id),
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "reason": self.reason,
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True, kw_only=True)
class RefundProcessed(DomainEvent):
    """The gateway answered. Booking updates its own refund record from this.

    One event for both outcomes, with a ``succeeded`` flag, because the
    consumer's work is the same shape either way — and a failed refund still
    needs the guest told something.
    """

    event_type: ClassVar[str] = "payment.refund.processed"
    aggregate_type: ClassVar[str] = AGGREGATE

    booking_id: uuid.UUID
    refund_id: uuid.UUID
    gateway_refund_id: str | None
    amount_minor: int
    currency: str
    succeeded: bool
    error: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "payment_id": str(self.aggregate_id),
            "booking_id": str(self.booking_id),
            "refund_id": str(self.refund_id),
            "gateway_refund_id": self.gateway_refund_id,
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "succeeded": self.succeeded,
            "error": self.error,
        }


@dataclass(frozen=True, kw_only=True)
class PaymentDisputed(DomainEvent):
    """A chargeback. Should page someone.

    The money is already gone — the network pulled it back — and a rising
    chargeback rate threatens the platform's ability to process cards at all.
    """

    event_type: ClassVar[str] = "payment.disputed"
    aggregate_type: ClassVar[str] = AGGREGATE

    booking_id: uuid.UUID
    booking_reference: str
    amount_minor: int
    currency: str
    reason: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "payment_id": str(self.aggregate_id),
            "booking_id": str(self.booking_id),
            "booking_reference": self.booking_reference,
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "reason": self.reason,
        }
