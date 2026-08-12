"""The booking module's published contract.

Payments needs two things from bookings: to know what a booking *should* cost,
and to tell it what happened to the money. Nothing else crosses.

**The dependency runs one way: payment → booking.** Booking never imports
payment. That is why booking emits ``RefundRequested`` rather than calling a
gateway, and why the amount cross-check lives here rather than payment reaching
into the booking aggregate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.core.types.money import Money


@dataclass(frozen=True, slots=True)
class BookingSnapshot:
    """What payments needs to charge for a booking, and nothing more.

    ``amount`` is the authority. Payments cross-checks every gateway callback
    against it, because the amount in a client-supplied callback is
    attacker-controlled and the amount in a webhook could belong to a different
    order entirely.
    """

    id: uuid.UUID
    reference: str
    guest_id: uuid.UUID
    guest_email: str
    guest_name: str
    guest_phone: str
    vendor_id: uuid.UUID
    property_name: str
    amount: Money
    status: str
    #: ``None`` once confirmed. While set, the hold is still running and a late
    #: payment must be refused and refunded rather than confirmed.
    hold_expires_at: datetime | None
    is_payable: bool
    #: The stay itself. Reviews need these as evidence: a review exists because
    #: a booking completed, and the review window is measured from checkout.
    property_id: uuid.UUID
    check_out: date
    #: True once the stay is over. Computed here rather than exposing the whole
    #: status vocabulary, so reviews cannot start depending on booking's
    #: internal states.
    is_reviewable: bool


class BookingPaymentService(Protocol):
    """How payments reports back.

    Every method runs inside the **caller's** transaction, so the payment row
    and the booking status move together. A payment recorded as captured
    against a booking that failed to confirm is the worst outcome available:
    the guest has paid and has no reservation.
    """

    async def snapshot(self, booking_id: uuid.UUID) -> BookingSnapshot | None: ...

    async def confirm_paid(
        self, *, booking_id: uuid.UUID, payment_id: str, paid_amount: Money
    ) -> str | None:
        """Confirm the booking. Returns the invoice number.

        Raises if the hold has expired — the inventory is gone and may have
        been resold, so the caller refunds instead of confirming.
        """
        ...

    async def record_refund_result(
        self,
        *,
        booking_id: uuid.UUID,
        succeeded: bool,
        gateway_refund_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """Close the loop on a refund the booking module asked for."""
        ...
