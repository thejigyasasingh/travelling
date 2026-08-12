"""The Booking aggregate: status machine, holds, cancellation, invoicing."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.core.types.money import Money
from app.modules.booking.domain import errors
from app.modules.booking.domain.entities import Booking
from app.modules.booking.domain.refund_policy import ChargeBreakdown, PolicyName
from app.modules.booking.domain.value_objects import (
    BookingReference,
    BookingStatus,
    CancelledBy,
    GuestDetails,
    HoldWindow,
    StayWindow,
)

pytestmark = pytest.mark.unit

INR = "INR"
NOW = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)
# Naive on purpose: StayWindow works in the property's wall-clock time.
LOCAL = datetime(2026, 6, 15, 15, 30)  # noqa: DTZ001
CHECK_IN = date(2026, 6, 20)
GUEST = uuid.uuid4()
VENDOR = uuid.uuid4()


def guest_details() -> GuestDetails:
    return GuestDetails(full_name="Priya Sharma", email="priya@example.com", phone="+919876543210")


def stay(check_in: date = CHECK_IN, nights: int = 3) -> StayWindow:
    return StayWindow(
        check_in_date=check_in,
        check_out_date=check_in + timedelta(days=nights),
        check_in_time=time(14, 0),
        check_out_time=time(11, 0),
    )


def charges(accommodation: int = 1_000_000, cleaning: int = 200_000, tax: int = 120_000):
    return ChargeBreakdown(
        accommodation=Money(accommodation, INR),
        extra_guest=Money.zero(INR),
        cleaning_fee=Money(cleaning, INR),
        tax=Money(tax, INR),
        platform_fee=Money.zero(INR),
    )


def make(**kw: object) -> Booking:
    defaults: dict[str, object] = {
        "guest_id": GUEST,
        "guest": guest_details(),
        "property_id": uuid.uuid4(),
        "property_name": "Sea Breeze Villa",
        "vendor_id": VENDOR,
        "room_type_id": uuid.uuid4(),
        "room_type_name": "Whole villa",
        "stay": stay(),
        "charges": charges(),
        "cancellation_policy": PolicyName.MODERATE,
        "now": NOW,
    }
    return Booking.hold_inventory(**{**defaults, **kw})  # type: ignore[arg-type]


class TestHold:
    def test_a_new_booking_holds_inventory_and_awaits_payment(self) -> None:
        booking = make()
        assert booking.status is BookingStatus.PENDING_PAYMENT
        assert booking.status.holds_inventory
        assert booking.hold is not None

    def test_a_request_to_book_awaits_approval_with_a_longer_window(self) -> None:
        # A human decision is measured in hours, not the 15 minutes a card
        # entry takes.
        instant = make()
        request = make(requires_approval=True)
        assert request.status is BookingStatus.PENDING_APPROVAL
        assert request.hold.expires_at > instant.hold.expires_at  # type: ignore[union-attr]

    def test_the_reference_is_readable_over_the_phone(self) -> None:
        # No 0/O, 1/I/L, 5/S or 8/B — a support agent transcribing a reference
        # must not have to guess.
        ref = str(make().reference)
        assert ref.startswith("RW-26-")
        assert not set(ref[6:]) & set("O0I1L5S8B")

    def test_references_are_unique_across_many_bookings(self) -> None:
        assert len({str(make().reference) for _ in range(200)}) == 200

    def test_holding_records_an_event_but_not_a_confirmation(self) -> None:
        # Nothing is paid yet. A premature confirmation email is worse than
        # none at all.
        types = [e.event_type for e in make().pull_events()]
        assert types == ["booking.held"]

    def test_the_policy_and_times_are_snapshotted(self) -> None:
        # A vendor changing their policy or check-in time tomorrow must not
        # alter what an existing guest agreed to.
        booking = make(cancellation_policy=PolicyName.STRICT)
        assert booking.cancellation_policy is PolicyName.STRICT
        assert booking.stay.check_in_time == time(14, 0)


class TestConfirmation:
    def test_confirming_within_the_window_succeeds(self) -> None:
        booking = make()
        booking.pull_events()
        booking.confirm(
            now=NOW + timedelta(minutes=5), payment_id="pay_123", invoice_number="INV/1"
        )

        assert booking.status is BookingStatus.CONFIRMED
        assert booking.payment_id == "pay_123"
        assert booking.hold is None  # no longer time-limited
        assert "booking.confirmed" in [e.event_type for e in booking.pull_events()]

    def test_confirming_after_the_hold_lapsed_is_refused(self) -> None:
        """A guest completing 3-D Secure at minute 16.

        The inventory is already released and may have been resold; confirming
        would create a booking with no room behind it.
        """
        booking = make()
        with pytest.raises(errors.HoldExpiredError):
            booking.confirm(now=NOW + timedelta(minutes=20), payment_id="pay_123")

    def test_confirming_twice_is_idempotent(self) -> None:
        # Gateways retry webhooks. A retry must not publish a second
        # confirmation email or issue a second invoice number.
        booking = make()
        booking.confirm(now=NOW, payment_id="pay_123", invoice_number="INV/1")
        booking.pull_events()

        booking.confirm(now=NOW + timedelta(minutes=1), payment_id="pay_123")
        assert booking.pull_events() == []
        assert booking.invoice_number == "INV/1"

    def test_a_cancelled_booking_cannot_be_confirmed(self) -> None:
        booking = make()
        booking.cancel(now_local=LOCAL, now=NOW, cancelled_by=CancelledBy.GUEST)
        with pytest.raises(errors.InvalidBookingTransitionError):
            booking.confirm(now=NOW, payment_id="pay_123")


class TestExpiry:
    def test_expiry_is_not_a_cancellation(self) -> None:
        """Nobody chose it.

        It must not appear in the guest's cancellation history, count against
        them in fraud scoring, or trigger a "sorry you cancelled" email.
        """
        booking = make()
        booking.pull_events()
        booking.expire(now=NOW + timedelta(minutes=20))

        assert booking.status is BookingStatus.EXPIRED
        assert not booking.status.holds_inventory
        assert [e.event_type for e in booking.pull_events()] == ["booking.expired"]

    def test_an_expired_booking_is_never_resurrected(self) -> None:
        # Its inventory is gone and may already have been resold.
        booking = make()
        booking.expire(now=NOW)
        with pytest.raises(errors.InvalidBookingTransitionError):
            booking.confirm(now=NOW, payment_id="pay_123")


class TestCancellation:
    def _confirmed(self) -> Booking:
        booking = make()
        booking.confirm(now=NOW, payment_id="pay_123", invoice_number="INV/1")
        booking.pull_events()
        return booking

    def test_cancelling_computes_the_refund_and_records_both_events(self) -> None:
        booking = self._confirmed()
        breakdown = booking.cancel(now_local=LOCAL, now=NOW, cancelled_by=CancelledBy.GUEST)

        assert booking.status is BookingStatus.CANCELLED
        assert breakdown.total.is_positive  # 5 days out under a moderate policy
        types = [e.event_type for e in booking.pull_events()]
        assert "booking.cancelled" in types
        assert "booking.refund.requested" in types

    def test_the_refund_uses_the_recorded_charges_not_current_rates(self) -> None:
        # A guest who paid ₹13,200 must be refunded against ₹13,200 even if the
        # vendor has since doubled their price.
        booking = self._confirmed()
        paid = booking.charges.total
        breakdown = booking.cancel(now_local=LOCAL, now=NOW, cancelled_by=CancelledBy.GUEST)
        assert breakdown.total + breakdown.vendor_retains == paid

    def test_an_unpaid_hold_refunds_nothing(self) -> None:
        # Nothing was ever captured, whatever the policy would allow.
        booking = make()
        breakdown = booking.cancel(now_local=LOCAL, now=NOW, cancelled_by=CancelledBy.GUEST)
        assert breakdown.total.is_zero
        assert breakdown.reason == "no_payment_captured"
        assert booking.refund is None

    def test_a_vendor_cancellation_refunds_in_full(self) -> None:
        booking = make(cancellation_policy=PolicyName.NON_REFUNDABLE)
        booking.confirm(now=NOW, payment_id="pay_123")
        breakdown = booking.cancel(
            now_local=LOCAL, now=NOW, cancelled_by=CancelledBy.VENDOR, reason="Flooding"
        )
        assert breakdown.is_full_refund

    def test_cancelling_twice_is_refused(self) -> None:
        booking = self._confirmed()
        booking.cancel(now_local=LOCAL, now=NOW, cancelled_by=CancelledBy.GUEST)
        with pytest.raises(errors.BookingNotCancellableError):
            booking.cancel(now_local=LOCAL, now=NOW, cancelled_by=CancelledBy.GUEST)

    def test_a_guest_cannot_cancel_a_stay_in_progress(self) -> None:
        # Leaving early is negotiated with the vendor, not refunded by us.
        booking = self._confirmed()
        booking.check_in(now=NOW)
        with pytest.raises(errors.BookingNotCancellableError):
            booking.cancel(now_local=LOCAL, now=NOW, cancelled_by=CancelledBy.GUEST)

    def test_a_vendor_can_cancel_a_stay_in_progress(self) -> None:
        booking = self._confirmed()
        booking.check_in(now=NOW)
        breakdown = booking.cancel(
            now_local=LOCAL, now=NOW, cancelled_by=CancelledBy.VENDOR, reason="Fire"
        )
        assert breakdown.is_full_refund

    def test_the_refund_request_carries_a_stable_idempotency_key(self) -> None:
        # A retried task, a duplicated outbox row and an impatient support
        # agent must all converge on one refund.
        booking = self._confirmed()
        booking.cancel(now_local=LOCAL, now=NOW, cancelled_by=CancelledBy.GUEST)
        event = next(e for e in booking.pull_events() if e.event_type == "booking.refund.requested")
        assert event.idempotency_key == f"refund-{booking.id}"

    def test_preview_does_not_change_anything(self) -> None:
        booking = self._confirmed()
        preview = booking.preview_refund(LOCAL)
        assert booking.status is BookingStatus.CONFIRMED
        assert preview.total.is_positive


class TestRefundLifecycle:
    def _cancelled(self) -> Booking:
        booking = make()
        booking.confirm(now=NOW, payment_id="pay_123")
        booking.cancel(now_local=LOCAL, now=NOW, cancelled_by=CancelledBy.GUEST)
        booking.pull_events()
        return booking

    def test_completing_a_refund_records_it(self) -> None:
        booking = self._cancelled()
        booking.mark_refund_completed(gateway_refund_id="rfnd_1", now=NOW)
        assert booking.refund.is_settled  # type: ignore[union-attr]
        assert "booking.refund.completed" in [e.event_type for e in booking.pull_events()]

    def test_completing_twice_is_idempotent(self) -> None:
        booking = self._cancelled()
        booking.mark_refund_completed(gateway_refund_id="rfnd_1", now=NOW)
        booking.pull_events()
        booking.mark_refund_completed(gateway_refund_id="rfnd_1", now=NOW)
        assert booking.pull_events() == []

    def test_a_failure_is_recorded_and_counted(self) -> None:
        # A guest owed money who has not received it escalates to a chargeback.
        booking = self._cancelled()
        booking.mark_refund_failed(error="insufficient balance", now=NOW)
        assert booking.refund.attempts == 1  # type: ignore[union-attr]
        assert "booking.refund.failed" in [e.event_type for e in booking.pull_events()]


class TestStayLifecycle:
    def test_check_in_then_complete(self) -> None:
        booking = make()
        booking.confirm(now=NOW, payment_id="pay_1")
        booking.check_in(now=NOW)
        assert booking.status is BookingStatus.IN_STAY

        booking.pull_events()
        booking.complete(now=NOW, platform_commission=Money(150_000, INR))
        assert booking.status is BookingStatus.COMPLETED

        event = next(e for e in booking.pull_events() if e.event_type == "booking.completed")
        # Payout excludes tax (the government's) and the platform's commission.
        assert event.payout_amount_minor == 1_320_000 - 120_000 - 150_000

    def test_a_no_show_still_held_the_room(self) -> None:
        booking = make()
        booking.confirm(now=NOW, payment_id="pay_1")
        booking.mark_no_show(now=NOW)
        assert booking.status.holds_inventory

    def test_completing_without_checking_in_is_refused(self) -> None:
        booking = make()
        booking.confirm(now=NOW, payment_id="pay_1")
        with pytest.raises(errors.InvalidBookingTransitionError):
            booking.complete(now=NOW, platform_commission=Money.zero(INR))


class TestAccess:
    def test_the_guest_may_see_their_own(self) -> None:
        make().assert_visible_to(user_id=GUEST, vendor_id=None)

    def test_the_owning_vendor_may_see_it(self) -> None:
        make().assert_visible_to(user_id=None, vendor_id=VENDOR)

    def test_staff_may_see_it(self) -> None:
        make().assert_visible_to(user_id=None, vendor_id=None, is_staff=True)

    def test_anyone_else_is_refused(self) -> None:
        # Surfaces as 404, not 403 — a 403 would confirm the reference exists.
        with pytest.raises(errors.BookingAccessDeniedError):
            make().assert_visible_to(user_id=uuid.uuid4(), vendor_id=uuid.uuid4())


class TestInvoicing:
    def test_an_invoice_can_be_attached_once_confirmed(self) -> None:
        booking = make()
        booking.confirm(now=NOW, payment_id="pay_1")
        booking.pull_events()
        booking.attach_invoice(number="RW/INV/2026-27/000001", now=NOW)
        assert "booking.invoice.issued" in [e.event_type for e in booking.pull_events()]

    def test_an_invoice_is_immutable_once_issued(self) -> None:
        # A correction is a credit note referencing it, never an edit.
        booking = make()
        booking.confirm(now=NOW, payment_id="pay_1", invoice_number="RW/INV/2026-27/000001")
        with pytest.raises(errors.InvoiceAlreadyIssuedError):
            booking.attach_invoice(number="RW/INV/2026-27/000002", now=NOW)

    def test_an_unpaid_booking_has_no_invoice(self) -> None:
        with pytest.raises(errors.InvoiceNotAvailableError):
            make().attach_invoice(number="RW/INV/2026-27/000001", now=NOW)


class TestValueObjects:
    def test_hours_until_check_in_uses_the_property_clock(self) -> None:
        """A date alone cannot answer "how long until check-in?".

        Checking in tomorrow at 14:00 is 30 hours away at 08:00 today, not
        "1 day" — and under a 24-hour policy that is the difference between a
        full refund and none.
        """
        window = stay(check_in=date(2026, 6, 16))
        local_8am = datetime(2026, 6, 15, 8, 0)  # noqa: DTZ001 — property wall clock
        assert window.hours_until_check_in(local_8am) == 30.0

    def test_a_malformed_reference_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Malformed"):
            BookingReference("NOT-A-REF")

    def test_the_hold_window_counts_down(self) -> None:
        window = HoldWindow.for_payment(NOW, minutes=15)
        assert window.seconds_remaining(NOW) == 900
        assert window.seconds_remaining(NOW + timedelta(minutes=20)) == 0
        assert window.is_expired(NOW + timedelta(minutes=16))

    def test_a_zero_night_stay_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="after check-in"):
            StayWindow(
                check_in_date=CHECK_IN,
                check_out_date=CHECK_IN,
                check_in_time=time(14, 0),
                check_out_time=time(11, 0),
            )
