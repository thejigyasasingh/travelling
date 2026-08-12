"""The Booking aggregate.

**Aggregate boundary.** ``Booking`` owns its charge breakdown, its refund and
its invoice. Those must be transactionally consistent with the booking's status
— a cancelled booking with no refund record, or a confirmed booking with no
invoice, is a reconciliation problem that surfaces weeks later in an accounts
report nobody can balance.

It does **not** own the inventory it holds. That lives in the property module
behind :class:`InventoryService`, because inventory is contended by every
booking for the same room and cannot be serialised behind one aggregate.

**The money invariant**, checked wherever amounts change: the charge components
sum to the total, and refunds never exceed what was paid. Both are also
enforced by database CHECK constraints, because an aggregate can only guard the
paths that go through it.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Final

from app.core.types.money import Money
from app.modules.booking.domain import errors
from app.modules.booking.domain.events import (
    BookingCancelled,
    BookingCheckedIn,
    BookingCompleted,
    BookingConfirmed,
    BookingExpired,
    BookingHeld,
    InvoiceIssued,
    RefundCompleted,
    RefundFailed,
    RefundRequested,
)
from app.modules.booking.domain.refund_policy import (
    ChargeBreakdown,
    PolicyName,
    RefundBreakdown,
    calculate_refund,
)
from app.modules.booking.domain.value_objects import (
    BookingReference,
    BookingStatus,
    CancelledBy,
    GuestDetails,
    HoldWindow,
    RefundStatus,
    StayWindow,
)
from app.shared.domain.entity import AggregateRoot

#: Legal status moves. Everything absent is refused — see
#: :class:`InvalidBookingTransitionError` for why this is modelled explicitly.
_TRANSITIONS: Final[dict[BookingStatus, frozenset[BookingStatus]]] = {
    BookingStatus.PENDING_PAYMENT: frozenset(
        {BookingStatus.CONFIRMED, BookingStatus.EXPIRED, BookingStatus.CANCELLED}
    ),
    BookingStatus.PENDING_APPROVAL: frozenset(
        {
            BookingStatus.PENDING_PAYMENT,
            BookingStatus.CONFIRMED,
            BookingStatus.REJECTED,
            BookingStatus.EXPIRED,
            BookingStatus.CANCELLED,
        }
    ),
    BookingStatus.CONFIRMED: frozenset(
        {BookingStatus.IN_STAY, BookingStatus.CANCELLED, BookingStatus.NO_SHOW}
    ),
    BookingStatus.IN_STAY: frozenset(
        # Cancellable mid-stay by a vendor or admin only — a guest leaving
        # early does not get an automatic refund.
        {BookingStatus.COMPLETED, BookingStatus.CANCELLED}
    ),
    # Terminal. An expired hold is never resurrected: its inventory is gone and
    # may already have been resold.
    BookingStatus.COMPLETED: frozenset(),
    BookingStatus.CANCELLED: frozenset(),
    BookingStatus.EXPIRED: frozenset(),
    BookingStatus.REJECTED: frozenset(),
    BookingStatus.NO_SHOW: frozenset({BookingStatus.COMPLETED}),
}

#: Below this, a "price change" is rounding noise from a rate edit and not
#: worth blocking a booking over. Above it, the guest sees the new number.
PRICE_TOLERANCE_MINOR: Final = 100  # ₹1


class Booking(AggregateRoot):
    """One reservation."""

    __slots__ = (
        "adults",
        "cancellation_policy",
        "cancellation_reason",
        "cancelled_at",
        "cancelled_by",
        "charges",
        "children",
        "confirmed_at",
        "created_at",
        "guest",
        "guest_id",
        "hold",
        "infants",
        "invoice_issued_at",
        "invoice_number",
        "nightly_rates",
        "payment_id",
        "property_id",
        "property_name",
        "reference",
        "refund",
        "room_type_id",
        "room_type_name",
        "rooms",
        "source",
        "status",
        "stay",
        "vendor_id",
    )

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        reference: BookingReference,
        guest_id: uuid.UUID,
        guest: GuestDetails,
        property_id: uuid.UUID,
        property_name: str,
        vendor_id: uuid.UUID,
        room_type_id: uuid.UUID,
        room_type_name: str,
        stay: StayWindow,
        charges: ChargeBreakdown,
        cancellation_policy: PolicyName,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        rooms: int = 1,
        status: BookingStatus = BookingStatus.PENDING_PAYMENT,
        hold: HoldWindow | None = None,
        nightly_rates: list[dict[str, object]] | None = None,
        payment_id: str | None = None,
        invoice_number: str | None = None,
        invoice_issued_at: datetime | None = None,
        refund: RefundRecord | None = None,
        confirmed_at: datetime | None = None,
        cancelled_at: datetime | None = None,
        cancelled_by: CancelledBy | None = None,
        cancellation_reason: str | None = None,
        source: str = "web",
        created_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(entity_id, version)
        self.reference = reference
        self.guest_id = guest_id
        self.guest = guest
        self.property_id = property_id
        self.property_name = property_name
        self.vendor_id = vendor_id
        self.room_type_id = room_type_id
        self.room_type_name = room_type_name
        self.stay = stay
        self.charges = charges
        self.cancellation_policy = cancellation_policy
        self.adults = adults
        self.children = children
        self.infants = infants
        self.rooms = rooms
        self.status = status
        self.hold = hold
        self.nightly_rates = nightly_rates or []
        self.payment_id = payment_id
        self.invoice_number = invoice_number
        self.invoice_issued_at = invoice_issued_at
        self.refund = refund
        self.confirmed_at = confirmed_at
        self.cancelled_at = cancelled_at
        self.cancelled_by = cancelled_by
        self.cancellation_reason = cancellation_reason
        self.source = source
        self.created_at = created_at

    # ── creation ──────────────────────────────────────────────────────────

    @classmethod
    def hold_inventory(
        cls,
        *,
        guest_id: uuid.UUID,
        guest: GuestDetails,
        property_id: uuid.UUID,
        property_name: str,
        vendor_id: uuid.UUID,
        room_type_id: uuid.UUID,
        room_type_name: str,
        stay: StayWindow,
        charges: ChargeBreakdown,
        cancellation_policy: PolicyName,
        now: datetime,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        rooms: int = 1,
        requires_approval: bool = False,
        nightly_rates: list[dict[str, object]] | None = None,
        hold_minutes: int = HoldWindow.DEFAULT_MINUTES,
        source: str = "web",
    ) -> Booking:
        """Create a booking that already holds its inventory.

        Named for what it *is*: by the time this returns, the caller has taken
        the rooms. The booking row and the inventory claim are written in one
        transaction — either both or neither.

        The property's policy, name, room name and check-in times are copied
        onto the booking rather than referenced. A vendor changing any of them
        tomorrow must not alter what an existing guest agreed to, and the
        invoice must still say what it said when it was issued.
        """
        status = (
            BookingStatus.PENDING_APPROVAL if requires_approval else BookingStatus.PENDING_PAYMENT
        )
        window = (
            HoldWindow.for_approval(now)
            if requires_approval
            else HoldWindow.for_payment(now, hold_minutes)
        )

        booking = cls(
            reference=BookingReference.generate(now.date()),
            guest_id=guest_id,
            guest=guest,
            property_id=property_id,
            property_name=property_name,
            vendor_id=vendor_id,
            room_type_id=room_type_id,
            room_type_name=room_type_name,
            stay=stay,
            charges=charges,
            cancellation_policy=cancellation_policy,
            adults=adults,
            children=children,
            infants=infants,
            rooms=rooms,
            status=status,
            hold=window,
            nightly_rates=nightly_rates,
            source=source,
            created_at=now,
        )
        booking.record(
            BookingHeld(
                aggregate_id=booking.id,
                reference=str(booking.reference),
                guest_id=guest_id,
                property_id=property_id,
                vendor_id=vendor_id,
                room_type_id=room_type_id,
                check_in=stay.check_in_date.isoformat(),
                check_out=stay.check_out_date.isoformat(),
                total_minor=charges.total.amount_minor,
                currency=charges.currency,
                expires_at=window.expires_at.isoformat(),
            )
        )
        return booking

    # ── access ────────────────────────────────────────────────────────────

    def assert_visible_to(
        self, *, user_id: uuid.UUID | None, vendor_id: uuid.UUID | None, is_staff: bool = False
    ) -> None:
        """The guest, the vendor who owns the property, or staff.

        Raises :class:`BookingAccessDeniedError`, which the interface maps to
        **404** — a 403 would confirm the reference exists and make the lookup
        endpoint an oracle for guessing them.
        """
        if is_staff:
            return
        if user_id is not None and self.guest_id == user_id:
            return
        if vendor_id is not None and self.vendor_id == vendor_id:
            return
        raise errors.BookingAccessDeniedError

    # ── status machine ────────────────────────────────────────────────────

    def _transition(self, target: BookingStatus) -> None:
        if target not in _TRANSITIONS.get(self.status, frozenset()):
            raise errors.InvalidBookingTransitionError(self.status.value, target.value)
        self.status = target

    @property
    def holds_inventory(self) -> bool:
        return self.status.holds_inventory

    def is_hold_expired(self, now: datetime) -> bool:
        return self.hold is not None and self.hold.is_expired(now)

    # ── confirmation ──────────────────────────────────────────────────────

    def confirm(
        self, *, now: datetime, payment_id: str | None, invoice_number: str | None = None
    ) -> None:
        """Payment succeeded.

        Re-checks the hold. A guest can complete 3-D Secure at minute 16 and
        the gateway calls back after the expiry job has already released the
        inventory — possibly to another guest. Confirming then would create a
        booking with no room behind it, so this raises and the caller refunds.
        """
        if self.is_hold_expired(now) and self.status is not BookingStatus.CONFIRMED:
            raise errors.HoldExpiredError

        if self.status is BookingStatus.CONFIRMED:
            return  # idempotent: gateways retry webhooks

        self._transition(BookingStatus.CONFIRMED)
        self.confirmed_at = now
        self.payment_id = payment_id
        self.hold = None  # no longer time-limited
        if invoice_number:
            self.invoice_number = invoice_number
            self.invoice_issued_at = now

        self.record(
            BookingConfirmed(
                aggregate_id=self.id,
                reference=str(self.reference),
                guest_id=self.guest_id,
                guest_email=self.guest.email,
                guest_name=self.guest.full_name,
                property_id=self.property_id,
                property_name=self.property_name,
                vendor_id=self.vendor_id,
                room_type_id=self.room_type_id,
                room_type_name=self.room_type_name,
                check_in=self.stay.check_in_date.isoformat(),
                check_out=self.stay.check_out_date.isoformat(),
                nights=self.stay.nights,
                guests=self.adults + self.children,
                rooms=self.rooms,
                total_minor=self.charges.total.amount_minor,
                currency=self.charges.currency,
                payment_id=payment_id,
                invoice_number=self.invoice_number,
            )
        )

    def approve(self, *, now: datetime) -> None:
        """Vendor accepted a request-to-book. The guest now has a payment
        window; the approval window is over."""
        self._transition(BookingStatus.PENDING_PAYMENT)
        self.hold = HoldWindow.for_payment(now)

    def reject(self, *, now: datetime, reason: str) -> None:
        self._transition(BookingStatus.REJECTED)
        self.cancelled_at = now
        self.cancelled_by = CancelledBy.VENDOR
        self.cancellation_reason = reason

    # ── expiry ────────────────────────────────────────────────────────────

    def expire(self, *, now: datetime) -> None:
        """The hold lapsed. Inventory is released by the caller.

        Deliberately not a cancellation: nobody chose it, so it must not appear
        in the guest's cancellation history, count against them in fraud
        scoring, or trigger a "sorry you cancelled" email.
        """
        self._transition(BookingStatus.EXPIRED)
        self.hold = None
        self.record(
            BookingExpired(
                aggregate_id=self.id,
                reference=str(self.reference),
                guest_id=self.guest_id,
                property_id=self.property_id,
                room_type_id=self.room_type_id,
                check_in=self.stay.check_in_date.isoformat(),
                check_out=self.stay.check_out_date.isoformat(),
            )
        )

    # ── cancellation ──────────────────────────────────────────────────────

    def cancel(
        self,
        *,
        now_local: datetime,
        now: datetime,
        cancelled_by: CancelledBy,
        reason: str | None = None,
    ) -> RefundBreakdown:
        """Cancel and compute what the guest gets back.

        The refund is calculated **here**, at cancellation time, from the
        charges recorded on the booking — never from today's rates. A guest who
        paid ₹47,000 must be refunded against ₹47,000 even if the vendor has
        since raised their price.

        ``now_local`` is the property's wall-clock time. Refund thresholds are
        "24 hours before check-in", and check-in is 14:00 *at the property* —
        computing that in UTC is wrong by hours in exactly the direction that
        generates complaints.
        """
        if not self.status.is_cancellable_by_guest and self.status is not BookingStatus.IN_STAY:
            raise errors.BookingNotCancellableError(self.status.value)
        if self.status is BookingStatus.IN_STAY and cancelled_by is CancelledBy.GUEST:
            # A guest leaving early negotiates with the vendor; the platform
            # does not compute a refund for an occupied room.
            raise errors.BookingNotCancellableError(self.status.value)

        hours_before = self.stay.hours_until_check_in(now_local)
        breakdown = calculate_refund(
            charges=self.charges,
            policy=self.cancellation_policy,
            hours_before_check_in=hours_before,
            cancelled_by=cancelled_by,
            stay_started=self.status is BookingStatus.IN_STAY,
        )

        # Nothing was captured yet on an unpaid hold, so there is nothing to
        # return regardless of what the policy would allow.
        if self.status in (BookingStatus.PENDING_PAYMENT, BookingStatus.PENDING_APPROVAL):
            breakdown = _zeroed(breakdown, currency=self.charges.currency)

        self._transition(BookingStatus.CANCELLED)
        self.cancelled_at = now
        self.cancelled_by = cancelled_by
        self.cancellation_reason = reason
        self.hold = None

        if breakdown.total.is_positive:
            self.refund = RefundRecord.pending(
                amount=breakdown.total, reason=breakdown.reason, booking_id=self.id
            )
            self.record(
                RefundRequested(
                    aggregate_id=self.id,
                    reference=str(self.reference),
                    payment_id=self.payment_id,
                    amount_minor=breakdown.total.amount_minor,
                    currency=breakdown.total.currency,
                    reason=breakdown.reason,
                    # Derived from the booking id, so a retried task or a
                    # double-clicked support button reaches the gateway with
                    # the same key and refunds once.
                    idempotency_key=f"refund-{self.id}",
                )
            )

        self.record(
            BookingCancelled(
                aggregate_id=self.id,
                reference=str(self.reference),
                guest_id=self.guest_id,
                guest_email=self.guest.email,
                property_id=self.property_id,
                vendor_id=self.vendor_id,
                cancelled_by=cancelled_by.value,
                reason=reason,
                refund_total_minor=breakdown.total.amount_minor,
                refund_breakdown=breakdown.to_payload(),
                currency=breakdown.total.currency,
                check_in=self.stay.check_in_date.isoformat(),
                hours_before_check_in=hours_before,
            )
        )
        return breakdown

    def preview_refund(self, now_local: datetime) -> RefundBreakdown:
        """What cancelling right now would return. No state change.

        Shown on the cancel screen. A guest who cancels and *then* learns the
        amount opens a support ticket; one who sees it first mostly does not.
        """
        return calculate_refund(
            charges=self.charges,
            policy=self.cancellation_policy,
            hours_before_check_in=self.stay.hours_until_check_in(now_local),
            cancelled_by=CancelledBy.GUEST,
            stay_started=self.status is BookingStatus.IN_STAY,
        )

    # ── refund lifecycle ──────────────────────────────────────────────────

    def mark_refund_completed(self, *, gateway_refund_id: str, now: datetime) -> None:
        if self.refund is None:  # pragma: no cover — guarded by the caller
            return
        if self.refund.is_settled:
            # Idempotent. Gateways retry webhooks, and recording the event
            # again would send the guest a second "your refund is on its way"
            # for money that already arrived.
            return
        self.refund.complete(gateway_refund_id=gateway_refund_id, now=now)
        self.record(
            RefundCompleted(
                aggregate_id=self.id,
                reference=str(self.reference),
                guest_email=self.guest.email,
                amount_minor=self.refund.amount.amount_minor,
                currency=self.refund.amount.currency,
                gateway_refund_id=gateway_refund_id,
            )
        )

    def mark_refund_failed(self, *, error: str, now: datetime) -> None:
        """A guest owed money who has not received it escalates to a
        chargeback, which costs far more than the refund. This event pages
        someone."""
        if self.refund is None:  # pragma: no cover
            return
        self.refund.fail(error=error, now=now)
        self.record(
            RefundFailed(
                aggregate_id=self.id,
                reference=str(self.reference),
                amount_minor=self.refund.amount.amount_minor,
                currency=self.refund.amount.currency,
                error=error,
                attempts=self.refund.attempts,
            )
        )

    # ── stay lifecycle ────────────────────────────────────────────────────

    def check_in(self, *, now: datetime) -> None:
        self._transition(BookingStatus.IN_STAY)
        self.record(
            BookingCheckedIn(
                aggregate_id=self.id,
                reference=str(self.reference),
                property_id=self.property_id,
            )
        )

    def complete(self, *, now: datetime, platform_commission: Money) -> None:
        """The stay ended. Releases the vendor payout.

        Held until after checkout on purpose: paying on confirmation would mean
        chasing a vendor for money back on every cancellation, and by then it
        is usually spent.
        """
        self._transition(BookingStatus.COMPLETED)
        payout = self.charges.total - self.charges.tax - platform_commission
        self.record(
            BookingCompleted(
                aggregate_id=self.id,
                reference=str(self.reference),
                guest_id=self.guest_id,
                property_id=self.property_id,
                vendor_id=self.vendor_id,
                payout_amount_minor=max(0, payout.amount_minor),
                currency=self.charges.currency,
            )
        )

    def mark_no_show(self, *, now: datetime) -> None:
        """The guest never arrived. Still holds inventory — the room was kept
        for them — and the vendor is normally paid in full."""
        self._transition(BookingStatus.NO_SHOW)

    # ── invoicing ─────────────────────────────────────────────────────────

    def attach_invoice(self, *, number: str, now: datetime) -> None:
        """Attach a tax invoice. Once numbered it is immutable — a correction
        is a credit note referencing it, never an edit."""
        if self.invoice_number is not None:
            raise errors.InvoiceAlreadyIssuedError(self.invoice_number)
        if self.status not in (
            BookingStatus.CONFIRMED,
            BookingStatus.IN_STAY,
            BookingStatus.COMPLETED,
        ):
            raise errors.InvoiceNotAvailableError(self.status.value)

        self.invoice_number = number
        self.invoice_issued_at = now
        self.record(
            InvoiceIssued(
                aggregate_id=self.id,
                reference=str(self.reference),
                invoice_number=number,
                guest_email=self.guest.email,
                total_minor=self.charges.total.amount_minor,
                tax_minor=self.charges.tax.amount_minor,
                currency=self.charges.currency,
            )
        )

    # ── accessors ─────────────────────────────────────────────────────────

    @property
    def total(self) -> Money:
        return self.charges.total

    @property
    def guest_count(self) -> int:
        return self.adults + self.children

    @property
    def refund_status(self) -> RefundStatus:
        return self.refund.status if self.refund else RefundStatus.NOT_APPLICABLE

    def is_upcoming(self, today: date) -> bool:
        return self.status in (
            BookingStatus.CONFIRMED,
            BookingStatus.PENDING_PAYMENT,
        ) and not self.stay.has_started(today)


class RefundRecord:
    """A refund in flight.

    A child of the booking rather than its own aggregate: it has no meaning
    apart from the booking, is never queried independently, and must change
    status in the same transaction as the booking it belongs to.
    """

    __slots__ = (
        "amount",
        "attempts",
        "booking_id",
        "completed_at",
        "gateway_refund_id",
        "last_error",
        "reason",
        "requested_at",
        "status",
    )

    def __init__(
        self,
        *,
        booking_id: uuid.UUID,
        amount: Money,
        reason: str,
        status: RefundStatus = RefundStatus.PENDING,
        gateway_refund_id: str | None = None,
        attempts: int = 0,
        last_error: str | None = None,
        requested_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        self.booking_id = booking_id
        self.amount = amount
        self.reason = reason
        self.status = status
        self.gateway_refund_id = gateway_refund_id
        self.attempts = attempts
        self.last_error = last_error
        self.requested_at = requested_at
        self.completed_at = completed_at

    @classmethod
    def pending(cls, *, booking_id: uuid.UUID, amount: Money, reason: str) -> RefundRecord:
        return cls(booking_id=booking_id, amount=amount, reason=reason)

    def complete(self, *, gateway_refund_id: str, now: datetime) -> None:
        if self.status is RefundStatus.COMPLETED:
            return  # idempotent: gateways retry webhooks
        self.status = RefundStatus.COMPLETED
        self.gateway_refund_id = gateway_refund_id
        self.completed_at = now

    def fail(self, *, error: str, now: datetime) -> None:
        self.status = RefundStatus.FAILED
        self.last_error = error[:500]
        self.attempts += 1

    @property
    def is_settled(self) -> bool:
        return self.status is RefundStatus.COMPLETED


def _zeroed(breakdown: RefundBreakdown, *, currency: str) -> RefundBreakdown:
    """Nothing was captured, so nothing is returned — but the reason is kept so
    the guest still sees why."""
    zero = Money.zero(currency)
    return RefundBreakdown(
        policy=breakdown.policy,
        hours_before_check_in=breakdown.hours_before_check_in,
        applied_percent=breakdown.applied_percent,
        accommodation=zero,
        extra_guest=zero,
        cleaning_fee=zero,
        tax=zero,
        platform_fee=zero,
        total=zero,
        vendor_retains=zero,
        reason="no_payment_captured",
        is_full_refund=False,
    )
