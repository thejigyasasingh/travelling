"""The Payment aggregate.

Every invariant here is about real money. The four that matter most:

* the **amount check** — the only thing stopping a ₹50,000 booking being
  confirmed against a ₹1 payment;
* **forward-only status**, so a redelivered ``payment.authorized`` cannot
  un-capture a payment;
* **refund idempotency**, so a retried task does not refund twice;
* the **ledger**, whose sum is the platform's real position and must match the
  settlement report.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.types.money import Money
from app.modules.payment.domain import errors
from app.modules.payment.domain.entities import Payment
from app.modules.payment.domain.value_objects import (
    PaymentMethod,
    PaymentStatus,
    TransactionKind,
)

pytestmark = pytest.mark.unit

INR = "INR"
NOW = datetime.now(UTC).replace(microsecond=0)
AMOUNT = Money(45_000_00, INR)  # ₹45,000


def make_payment(amount: Money = AMOUNT) -> Payment:
    return Payment.create_order(
        booking_id=uuid.uuid4(),
        booking_reference="RW7QK4XM",
        guest_id=uuid.uuid4(),
        amount=amount,
        gateway_order_id="order_MkL9pQrStUvWxY",
    )


def capture(payment: Payment, *, fee: Money | None = None, tax: Money | None = None) -> None:
    payment.mark_captured(
        gateway_payment_id="pay_MkL9pQrStUvWxZ",
        amount=payment.expected_amount,
        method=PaymentMethod.UPI,
        now=NOW,
        fee=fee,
        tax=tax,
        vpa_or_last4="guest@okhdfcbank",
    )


# ══════════════════════════════════════════════════════════════════════════
# The amount check
# ══════════════════════════════════════════════════════════════════════════


def test_capturing_a_smaller_amount_is_refused() -> None:
    """The attack this module exists to stop: pay ₹1, get a ₹45,000 stay."""
    payment = make_payment()
    with pytest.raises(errors.AmountMismatchError):
        payment.mark_captured(
            gateway_payment_id="pay_x",
            amount=Money(100, INR),
            method=PaymentMethod.CARD,
            now=NOW,
        )
    assert payment.status is PaymentStatus.CREATED


def test_capturing_a_larger_amount_is_also_refused() -> None:
    """Not "at least the expected amount" — exactly it.

    An overpayment is a bug or a tampered order, and confirming it silently
    leaves the platform holding money it has no basis to keep.
    """
    payment = make_payment()
    with pytest.raises(errors.AmountMismatchError):
        payment.mark_captured(
            gateway_payment_id="pay_x",
            amount=Money(50_000_00, INR),
            method=PaymentMethod.CARD,
            now=NOW,
        )


def test_a_different_currency_is_a_mismatch_even_at_the_same_number() -> None:
    """4500000 paise is not 4500000 of anything else."""
    payment = make_payment()
    with pytest.raises(errors.AmountMismatchError):
        payment.assert_amount_matches(Money(AMOUNT.amount_minor, "USD"))


# ══════════════════════════════════════════════════════════════════════════
# Status: forward only
# ══════════════════════════════════════════════════════════════════════════


def test_auto_capture_may_skip_authorized() -> None:
    """With auto-capture on, ``payment.authorized`` may never arrive at all."""
    payment = make_payment()
    capture(payment)
    assert payment.status is PaymentStatus.CAPTURED


def test_a_late_authorized_event_cannot_un_capture() -> None:
    """The out-of-order case that happens in production every day.

    Razorpay delivers ``captured`` and ``authorized`` with no ordering
    guarantee. Applying the stale one would move a paid booking backwards.
    """
    payment = make_payment()
    capture(payment)

    applied = payment.mark_authorized(
        gateway_payment_id="pay_MkL9pQrStUvWxZ",
        amount=AMOUNT,
        method=PaymentMethod.UPI,
        now=NOW + timedelta(seconds=5),
        strict=False,
    )
    assert applied is False
    assert payment.status is PaymentStatus.CAPTURED


def test_a_stale_event_raises_under_strict_and_is_ignored_under_non_strict() -> None:
    """Two callers, two needs.

    The checkout path is strict — a client sending an impossible transition is
    an error worth surfacing. The webhook path is not, because rejecting a
    redelivery makes Razorpay send it forever.
    """
    payment = make_payment()
    capture(payment)

    with pytest.raises(errors.InvalidPaymentTransitionError):
        payment.mark_failed(code="BAD_REQUEST_ERROR", reason="late", now=NOW, strict=True)

    assert payment.mark_failed(code="x", reason="y", now=NOW, strict=False) is False
    assert payment.status is PaymentStatus.CAPTURED


def test_a_failed_payment_is_terminal() -> None:
    """No revival. The guest retries, which creates a *new* payment."""
    payment = make_payment()
    payment.mark_failed(code="GATEWAY_ERROR", reason="declined", now=NOW)

    with pytest.raises(errors.InvalidPaymentTransitionError):
        capture(payment)


def test_re_applying_the_same_status_is_a_no_op_not_an_error() -> None:
    """Duplicate webhooks are normal traffic."""
    payment = make_payment()
    capture(payment)
    assert (
        payment.mark_captured(
            gateway_payment_id="pay_MkL9pQrStUvWxZ",
            amount=AMOUNT,
            method=PaymentMethod.UPI,
            now=NOW,
            strict=False,
        )
        is False
    )
    # And crucially, no second charge entry.
    charges = [e for e in payment.ledger if e.kind is TransactionKind.CHARGE]
    assert len(charges) == 1


# ══════════════════════════════════════════════════════════════════════════
# Refunds
# ══════════════════════════════════════════════════════════════════════════


def test_refunding_more_than_was_captured_is_refused() -> None:
    payment = make_payment()
    capture(payment)
    with pytest.raises(errors.RefundExceedsCapturedError):
        payment.request_refund(
            amount=Money(50_000_00, INR), reason="goodwill", idempotency_key="k1", now=NOW
        )


def test_refunding_an_uncaptured_payment_is_refused() -> None:
    """Money that never moved cannot come back."""
    payment = make_payment()
    with pytest.raises(errors.RefundExceedsCapturedError):
        payment.request_refund(amount=Money(100, INR), reason="oops", idempotency_key="k1", now=NOW)


def test_the_same_idempotency_key_returns_the_original_attempt() -> None:
    """The in-process half of the double-refund guard.

    The other halves are a unique constraint on ``(payment_id,
    idempotency_key)`` and the same key sent to Razorpay as a header — three
    independent layers, because a double refund is unrecoverable in practice.
    """
    payment = make_payment()
    capture(payment)

    first = payment.request_refund(
        amount=Money(10_000_00, INR), reason="cancellation", idempotency_key="refund-b1", now=NOW
    )
    second = payment.request_refund(
        amount=Money(10_000_00, INR), reason="cancellation", idempotency_key="refund-b1", now=NOW
    )
    assert first is second
    assert len(payment.refunds) == 1


def test_two_partial_refunds_cannot_exceed_the_capture_together() -> None:
    payment = make_payment()
    capture(payment)

    payment.request_refund(
        amount=Money(30_000_00, INR), reason="partial", idempotency_key="r1", now=NOW
    )
    with pytest.raises(errors.RefundExceedsCapturedError):
        payment.request_refund(
            amount=Money(20_000_00, INR), reason="second", idempotency_key="r2", now=NOW
        )


def test_a_partial_refund_leaves_the_rest_refundable() -> None:
    payment = make_payment()
    capture(payment)
    payment.request_refund(
        amount=Money(15_000_00, INR), reason="partial", idempotency_key="r1", now=NOW
    )
    payment.mark_refund_processed(idempotency_key="r1", gateway_refund_id="rfnd_1", now=NOW)

    assert payment.status is PaymentStatus.PARTIALLY_REFUNDED
    assert payment.refunded_amount == Money(15_000_00, INR)
    assert payment.refundable_amount == Money(30_000_00, INR)


def test_a_full_refund_moves_to_refunded() -> None:
    payment = make_payment()
    capture(payment)
    payment.request_refund(amount=AMOUNT, reason="cancellation", idempotency_key="r1", now=NOW)
    payment.mark_refund_processed(idempotency_key="r1", gateway_refund_id="rfnd_1", now=NOW)

    assert payment.status is PaymentStatus.REFUNDED
    assert payment.refundable_amount.is_zero


def test_a_redelivered_refund_webhook_posts_no_second_ledger_entry() -> None:
    """Razorpay redelivers refund webhooks like any other.

    A second REFUND entry would make the ledger say the platform returned twice
    what it did, and the settlement report would never balance again.
    """
    payment = make_payment()
    capture(payment)
    payment.request_refund(amount=AMOUNT, reason="cancel", idempotency_key="r1", now=NOW)

    assert (
        payment.mark_refund_processed(idempotency_key="r1", gateway_refund_id="rfnd_1", now=NOW)
        is True
    )
    assert (
        payment.mark_refund_processed(idempotency_key="r1", gateway_refund_id="rfnd_1", now=NOW)
        is False
    )

    refunds = [e for e in payment.ledger if e.kind is TransactionKind.REFUND]
    assert len(refunds) == 1


def test_a_failed_refund_frees_the_amount_to_be_retried() -> None:
    """Failed refunds do not count against the refundable balance — the money
    never left, and treating it as gone would strand the guest."""
    payment = make_payment()
    capture(payment)
    payment.request_refund(amount=AMOUNT, reason="cancel", idempotency_key="r1", now=NOW)
    payment.mark_refund_failed(idempotency_key="r1", error="gateway timeout", now=NOW)

    assert payment.refundable_amount == AMOUNT
    assert payment.status is PaymentStatus.CAPTURED


def test_a_pending_refund_does_count_against_the_balance() -> None:
    """The opposite bias from a failed one, on purpose: a refund in flight may
    still succeed, and issuing a second one meanwhile would return the money
    twice."""
    payment = make_payment()
    capture(payment)
    payment.request_refund(amount=AMOUNT, reason="cancel", idempotency_key="r1", now=NOW)

    assert payment.refundable_amount.is_zero


def test_an_unknown_idempotency_key_settles_nothing() -> None:
    payment = make_payment()
    capture(payment)
    assert (
        payment.mark_refund_processed(
            idempotency_key="never-requested", gateway_refund_id="rfnd_x", now=NOW
        )
        is False
    )


# ══════════════════════════════════════════════════════════════════════════
# The ledger
# ══════════════════════════════════════════════════════════════════════════


def test_capture_posts_the_charge_the_fee_and_the_tax_separately() -> None:
    """Fees are not part of what the guest paid, but they are part of what the
    platform receives. A reconciliation that ignores them never balances."""
    payment = make_payment()
    capture(payment, fee=Money(900_00, INR), tax=Money(162_00, INR))

    kinds = [e.kind for e in payment.ledger]
    assert kinds == [
        TransactionKind.CHARGE,
        TransactionKind.GATEWAY_FEE,
        TransactionKind.GATEWAY_TAX,
    ]


def test_net_position_is_the_sum_of_the_ledger() -> None:
    """₹45,000 in, ₹900 fee, ₹162 tax, ₹15,000 refunded → ₹28,938 held."""
    payment = make_payment()
    capture(payment, fee=Money(900_00, INR), tax=Money(162_00, INR))
    payment.request_refund(
        amount=Money(15_000_00, INR), reason="partial", idempotency_key="r1", now=NOW
    )
    payment.mark_refund_processed(idempotency_key="r1", gateway_refund_id="rfnd_1", now=NOW)

    assert payment.net_position == Money(45_000_00 - 900_00 - 162_00 - 15_000_00, INR)


def test_only_the_charge_is_positive() -> None:
    """The sign convention the database CHECK also enforces: without it, a SUM
    over the ledger is silently wrong in a way nobody notices until month end."""
    payment = make_payment()
    capture(payment, fee=Money(900_00, INR))
    payment.request_refund(amount=Money(100_00, INR), reason="x", idempotency_key="r1", now=NOW)
    payment.mark_refund_processed(idempotency_key="r1", gateway_refund_id="rfnd_1", now=NOW)
    payment.mark_disputed(amount=Money(1_000_00, INR), now=NOW, reason="fraud")

    for entry in payment.ledger:
        if entry.kind is TransactionKind.CHARGE:
            assert entry.signed_amount.amount_minor > 0
        else:
            assert entry.signed_amount.amount_minor < 0


def test_a_chargeback_is_recorded_not_treated_as_a_refund() -> None:
    """Different accounting, different fraud signal. Collapsing the two hides a
    rising chargeback rate, which is what gets card processing withdrawn."""
    payment = make_payment()
    capture(payment)
    payment.mark_disputed(amount=AMOUNT, now=NOW, reason="fraud")

    assert payment.status is PaymentStatus.DISPUTED
    assert [e.kind for e in payment.ledger] == [
        TransactionKind.CHARGE,
        TransactionKind.CHARGEBACK,
    ]
    assert payment.net_position.is_zero


# ══════════════════════════════════════════════════════════════════════════
# Retry
# ══════════════════════════════════════════════════════════════════════════


def test_retrying_a_paid_payment_is_refused() -> None:
    """The double-charge guard on the retry path."""
    payment = make_payment()
    capture(payment)
    with pytest.raises(errors.RetryNotAllowedError):
        payment.assert_can_retry()


def test_a_failed_payment_may_be_retried() -> None:
    payment = make_payment()
    payment.mark_failed(code="GATEWAY_ERROR", reason="declined", now=NOW)
    payment.assert_can_retry()  # does not raise


def test_an_authorized_payment_may_not_be_retried() -> None:
    """The money is reserved; a retry would reserve it twice."""
    payment = make_payment()
    payment.mark_authorized(
        gateway_payment_id="pay_x", amount=AMOUNT, method=PaymentMethod.CARD, now=NOW
    )
    with pytest.raises(errors.RetryNotAllowedError):
        payment.assert_can_retry()


# ══════════════════════════════════════════════════════════════════════════


def test_creating_an_order_records_the_event() -> None:
    payment = make_payment()
    events = payment.pull_events()
    assert [type(e).__name__ for e in events] == ["PaymentOrderCreated"]
    # Pulled once, gone — the outbox owns them from here.
    assert payment.pull_events() == []


def test_no_card_number_is_ever_stored() -> None:
    """Only a last-4 or a VPA reaches this aggregate. A PAN would pull the whole
    platform into PCI-DSS scope for cardholder data."""
    payment = make_payment()
    capture(payment)
    assert payment.vpa_or_last4 == "guest@okhdfcbank"
    assert len(payment.vpa_or_last4 or "") <= 64
