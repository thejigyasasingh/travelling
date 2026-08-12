"""Booking domain events.

The booking module is the hub of the platform, so its events have the widest
consumer list: notification (guest and vendor mail), payment (capture and
refund), payout (vendor settlement), search (availability invalidation),
analytics, and the vendor's channel-manager sync.

None of those modules are imported here. That is the entire point — adding a
sixth consumer touches no booking code.

Every payload carries the **booking reference**, not just the id: it is what a
guest quotes to support and what appears in an email, so a consumer that needs
to render anything user-facing should not have to look it up.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

from app.shared.domain.events import DomainEvent

AGGREGATE = "booking"


@dataclass(frozen=True, kw_only=True)
class BookingHeld(DomainEvent):
    """Inventory is taken and the clock is running.

    Consumers: notification (a "complete your booking" nudge before expiry),
    analytics (checkout funnel). Deliberately *not* the confirmation email —
    nothing is paid yet, and a premature confirmation is worse than none.
    """

    event_type: ClassVar[str] = "booking.held"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    guest_id: uuid.UUID
    property_id: uuid.UUID
    vendor_id: uuid.UUID
    room_type_id: uuid.UUID
    check_in: str
    check_out: str
    total_minor: int
    currency: str
    expires_at: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "booking_id": str(self.aggregate_id),
            "reference": self.reference,
            "guest_id": str(self.guest_id),
            "property_id": str(self.property_id),
            "vendor_id": str(self.vendor_id),
            "room_type_id": str(self.room_type_id),
            "check_in": self.check_in,
            "check_out": self.check_out,
            "total_minor": self.total_minor,
            "currency": self.currency,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True, kw_only=True)
class BookingConfirmed(DomainEvent):
    """Paid and committed. The event with the most consumers in the system.

    Notification sends the guest their confirmation and the vendor their
    arrival notice; payout schedules the vendor's settlement; the channel
    manager pushes the block to Booking.com and Airbnb so the same room is not
    sold twice across platforms.
    """

    event_type: ClassVar[str] = "booking.confirmed"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    guest_id: uuid.UUID
    guest_email: str
    guest_name: str
    property_id: uuid.UUID
    property_name: str
    vendor_id: uuid.UUID
    room_type_id: uuid.UUID
    room_type_name: str
    check_in: str
    check_out: str
    nights: int
    guests: int
    rooms: int
    total_minor: int
    currency: str
    payment_id: str | None
    invoice_number: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "booking_id": str(self.aggregate_id),
            "reference": self.reference,
            "guest_id": str(self.guest_id),
            "guest_email": self.guest_email,
            "guest_name": self.guest_name,
            "property_id": str(self.property_id),
            "property_name": self.property_name,
            "vendor_id": str(self.vendor_id),
            "room_type_id": str(self.room_type_id),
            "room_type_name": self.room_type_name,
            "check_in": self.check_in,
            "check_out": self.check_out,
            "nights": self.nights,
            "guests": self.guests,
            "rooms": self.rooms,
            "total_minor": self.total_minor,
            "currency": self.currency,
            "payment_id": self.payment_id,
            "invoice_number": self.invoice_number,
        }


@dataclass(frozen=True, kw_only=True)
class BookingCancelled(DomainEvent):
    """Carries the full refund breakdown.

    The payment module needs the amount; notification needs the itemisation to
    explain it; payout needs to know what the vendor still retains. Shipping
    the breakdown means none of them has to recompute it — and three
    independent recomputations would eventually disagree.
    """

    event_type: ClassVar[str] = "booking.cancelled"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    guest_id: uuid.UUID
    guest_email: str
    property_id: uuid.UUID
    vendor_id: uuid.UUID
    cancelled_by: str
    reason: str | None
    refund_total_minor: int
    refund_breakdown: dict[str, Any]
    currency: str
    check_in: str
    hours_before_check_in: float

    def to_payload(self) -> dict[str, Any]:
        return {
            "booking_id": str(self.aggregate_id),
            "reference": self.reference,
            "guest_id": str(self.guest_id),
            "guest_email": self.guest_email,
            "property_id": str(self.property_id),
            "vendor_id": str(self.vendor_id),
            "cancelled_by": self.cancelled_by,
            "reason": self.reason,
            "refund_total_minor": self.refund_total_minor,
            "refund_breakdown": self.refund_breakdown,
            "currency": self.currency,
            "check_in": self.check_in,
            "hours_before_check_in": self.hours_before_check_in,
        }


@dataclass(frozen=True, kw_only=True)
class BookingExpired(DomainEvent):
    """A hold lapsed. Inventory is already released by the time this is
    published.

    Separate from ``BookingCancelled`` because nobody chose it: it must not
    appear in a guest's cancellation history, count against them in fraud
    scoring, or trigger a "sorry you cancelled" email.
    """

    event_type: ClassVar[str] = "booking.expired"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    guest_id: uuid.UUID
    property_id: uuid.UUID
    room_type_id: uuid.UUID
    check_in: str
    check_out: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "booking_id": str(self.aggregate_id),
            "reference": self.reference,
            "guest_id": str(self.guest_id),
            "property_id": str(self.property_id),
            "room_type_id": str(self.room_type_id),
            "check_in": self.check_in,
            "check_out": self.check_out,
        }


@dataclass(frozen=True, kw_only=True)
class RefundRequested(DomainEvent):
    """Hands the payment module an amount to return.

    Carries ``idempotency_key`` because a retried task must not refund twice —
    the gateway is the only thing that can guarantee that, and only if we give
    it the same key.
    """

    event_type: ClassVar[str] = "booking.refund.requested"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    payment_id: str | None
    amount_minor: int
    currency: str
    reason: str
    idempotency_key: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "booking_id": str(self.aggregate_id),
            "reference": self.reference,
            "payment_id": self.payment_id,
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "reason": self.reason,
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True, kw_only=True)
class RefundCompleted(DomainEvent):
    event_type: ClassVar[str] = "booking.refund.completed"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    guest_email: str
    amount_minor: int
    currency: str
    gateway_refund_id: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "booking_id": str(self.aggregate_id),
            "reference": self.reference,
            "guest_email": self.guest_email,
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "gateway_refund_id": self.gateway_refund_id,
        }


@dataclass(frozen=True, kw_only=True)
class RefundFailed(DomainEvent):
    """The gateway refused. Needs a human, and quickly.

    A guest owed money who has not received it escalates to a chargeback, which
    costs far more than the refund and damages the platform's processing
    reputation.
    """

    event_type: ClassVar[str] = "booking.refund.failed"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    amount_minor: int
    currency: str
    error: str
    attempts: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "booking_id": str(self.aggregate_id),
            "reference": self.reference,
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "error": self.error,
            "attempts": self.attempts,
        }


@dataclass(frozen=True, kw_only=True)
class InvoiceIssued(DomainEvent):
    """A tax invoice exists and is immutable from this moment."""

    event_type: ClassVar[str] = "booking.invoice.issued"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    invoice_number: str
    guest_email: str
    total_minor: int
    tax_minor: int
    currency: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "booking_id": str(self.aggregate_id),
            "reference": self.reference,
            "invoice_number": self.invoice_number,
            "guest_email": self.guest_email,
            "total_minor": self.total_minor,
            "tax_minor": self.tax_minor,
            "currency": self.currency,
        }


@dataclass(frozen=True, kw_only=True)
class BookingCheckedIn(DomainEvent):
    event_type: ClassVar[str] = "booking.checked_in"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    property_id: uuid.UUID

    def to_payload(self) -> dict[str, Any]:
        return {
            "booking_id": str(self.aggregate_id),
            "reference": self.reference,
            "property_id": str(self.property_id),
        }


@dataclass(frozen=True, kw_only=True)
class BookingCompleted(DomainEvent):
    """The stay ended. Releases the vendor payout and opens the review window.

    The payout is deliberately held until *after* checkout: paying on
    confirmation would mean chasing a vendor for money back when the guest
    cancels, and that money is usually already spent.
    """

    event_type: ClassVar[str] = "booking.completed"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    guest_id: uuid.UUID
    property_id: uuid.UUID
    vendor_id: uuid.UUID
    payout_amount_minor: int
    currency: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "booking_id": str(self.aggregate_id),
            "reference": self.reference,
            "guest_id": str(self.guest_id),
            "property_id": str(self.property_id),
            "vendor_id": str(self.vendor_id),
            "payout_amount_minor": self.payout_amount_minor,
            "currency": self.currency,
        }
