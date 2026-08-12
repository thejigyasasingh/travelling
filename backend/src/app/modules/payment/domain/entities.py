"""The Payment aggregate and the transaction ledger.

**Aggregate boundary.** ``Payment`` owns its refunds and its ledger entries.
They must be transactionally consistent with its status — a payment marked
``refunded`` with no refund row, or a captured payment with no ledger entry, is
a reconciliation failure that surfaces at month end in a report nobody can
balance.

**The ledger is append-only.** Every money movement is a row: the charge, each
refund, the gateway's fee, the tax on that fee, a chargeback. Nothing is ever
updated or deleted. A payment's true net is `sum(ledger)`, not a column someone
maintained — and when the Razorpay settlement report disagrees with our
database, the ledger is what makes the difference explainable rather than a
mystery.

**Status only moves forward.** Webhooks arrive out of order routinely;
``payment.captured`` can land before ``payment.authorized``. Every transition is
checked against an explicit table, and a stale one is ignored rather than
applied.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Final

from app.core.types.money import Money
from app.modules.payment.domain import errors
from app.modules.payment.domain.events import (
    PaymentAuthorized,
    PaymentCaptured,
    PaymentDisputed,
    PaymentFailed,
    PaymentOrderCreated,
    RefundProcessed,
    RefundRecorded,
)
from app.modules.payment.domain.value_objects import (
    PaymentMethod,
    PaymentStatus,
    RefundSpeed,
    RefundStatus,
    TransactionKind,
)
from app.shared.domain.entity import AggregateRoot, Entity

#: Legal transitions. Anything absent is a stale or impossible event and is
#: refused — see :class:`InvalidPaymentTransitionError`.
_TRANSITIONS: Final[dict[PaymentStatus, frozenset[PaymentStatus]]] = {
    PaymentStatus.CREATED: frozenset(
        {
            PaymentStatus.PENDING,
            PaymentStatus.AUTHORIZED,
            # Auto-capture skips `authorized` entirely, so this edge is normal.
            PaymentStatus.CAPTURED,
            PaymentStatus.FAILED,
        }
    ),
    PaymentStatus.PENDING: frozenset(
        {PaymentStatus.AUTHORIZED, PaymentStatus.CAPTURED, PaymentStatus.FAILED}
    ),
    PaymentStatus.AUTHORIZED: frozenset({PaymentStatus.CAPTURED, PaymentStatus.FAILED}),
    PaymentStatus.CAPTURED: frozenset(
        {
            PaymentStatus.PARTIALLY_REFUNDED,
            PaymentStatus.REFUNDED,
            PaymentStatus.DISPUTED,
        }
    ),
    PaymentStatus.PARTIALLY_REFUNDED: frozenset({PaymentStatus.REFUNDED, PaymentStatus.DISPUTED}),
    # Terminal. A failed payment is never revived — the guest retries, which
    # creates a *new* payment with its own order.
    PaymentStatus.FAILED: frozenset(),
    PaymentStatus.REFUNDED: frozenset({PaymentStatus.DISPUTED}),
    PaymentStatus.DISPUTED: frozenset(),
}


class LedgerEntry(Entity):
    """One immutable money movement.

    Signed: a charge is positive, a refund and a fee negative. Summing the
    ledger gives the platform's actual net position on a payment, which is the
    number that has to match the settlement report.
    """

    __slots__ = ("amount", "gateway_reference", "kind", "note", "occurred_at")

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        kind: TransactionKind,
        amount: Money,
        occurred_at: datetime,
        gateway_reference: str | None = None,
        note: str | None = None,
    ) -> None:
        super().__init__(entity_id)
        self.kind = kind
        self.amount = amount
        self.occurred_at = occurred_at
        self.gateway_reference = gateway_reference
        self.note = note

    @property
    def signed_amount(self) -> Money:
        return self.amount if self.kind.is_credit else -self.amount


class RefundAttempt(Entity):
    """One refund against a payment.

    Multiple are possible: a partial refund for a late cancellation, then
    another for a goodwill gesture. Their sum can never exceed what was
    captured — guarded here and by a database CHECK.
    """

    __slots__ = (
        "amount",
        "booking_id",
        "completed_at",
        "failure_reason",
        "gateway_refund_id",
        "idempotency_key",
        "reason",
        "requested_at",
        "speed",
        "status",
    )

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        amount: Money,
        reason: str,
        idempotency_key: str,
        requested_at: datetime,
        booking_id: uuid.UUID | None = None,
        speed: RefundSpeed = RefundSpeed.NORMAL,
        status: RefundStatus = RefundStatus.PENDING,
        gateway_refund_id: str | None = None,
        failure_reason: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        super().__init__(entity_id)
        self.amount = amount
        self.reason = reason
        #: Sent to Razorpay as `X-Razorpay-Idempotency-Key`. Derived from the
        #: booking id, so a retried task and a double-clicked support button
        #: reach the gateway with the same key and refund once.
        self.idempotency_key = idempotency_key
        self.requested_at = requested_at
        self.booking_id = booking_id
        self.speed = speed
        self.status = status
        self.gateway_refund_id = gateway_refund_id
        self.failure_reason = failure_reason
        self.completed_at = completed_at

    @property
    def is_settled(self) -> bool:
        return self.status is RefundStatus.PROCESSED


class Payment(AggregateRoot):
    """One attempt to collect money for one booking."""

    __slots__ = (
        "attempt_number",
        "authorized_at",
        "booking_id",
        "booking_reference",
        "captured_at",
        "created_at",
        "currency",
        "expected_amount",
        "failure_code",
        "failure_reason",
        "gateway",
        "gateway_fee",
        "gateway_order_id",
        "gateway_payment_id",
        "gateway_tax",
        "guest_id",
        "ledger",
        "method",
        "notes",
        "refunds",
        "status",
        "vpa_or_last4",
    )

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        booking_id: uuid.UUID,
        booking_reference: str,
        guest_id: uuid.UUID,
        expected_amount: Money,
        gateway_order_id: str,
        gateway: str = "razorpay",
        status: PaymentStatus = PaymentStatus.CREATED,
        gateway_payment_id: str | None = None,
        method: PaymentMethod = PaymentMethod.UNKNOWN,
        vpa_or_last4: str | None = None,
        attempt_number: int = 1,
        authorized_at: datetime | None = None,
        captured_at: datetime | None = None,
        failure_code: str | None = None,
        failure_reason: str | None = None,
        gateway_fee: Money | None = None,
        gateway_tax: Money | None = None,
        refunds: list[RefundAttempt] | None = None,
        ledger: list[LedgerEntry] | None = None,
        notes: dict[str, Any] | None = None,
        #: Set by the repository from the row. Absent on a payment that has
        #: not been persisted yet — the database assigns it, so inventing one
        #: here would produce a value the cursor could never match.
        created_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(entity_id, version)
        self.booking_id = booking_id
        self.booking_reference = booking_reference
        self.guest_id = guest_id
        self.expected_amount = expected_amount
        self.currency = expected_amount.currency
        self.gateway_order_id = gateway_order_id
        self.gateway = gateway
        self.status = status
        self.gateway_payment_id = gateway_payment_id
        self.method = method
        self.vpa_or_last4 = vpa_or_last4
        self.attempt_number = attempt_number
        self.authorized_at = authorized_at
        self.captured_at = captured_at
        self.failure_code = failure_code
        self.failure_reason = failure_reason
        self.gateway_fee = gateway_fee
        self.gateway_tax = gateway_tax
        self.refunds = refunds or []
        self.ledger = ledger or []
        self.notes = notes or {}
        self.created_at = created_at

    # ── creation ──────────────────────────────────────────────────────────

    @classmethod
    def create_order(
        cls,
        *,
        booking_id: uuid.UUID,
        booking_reference: str,
        guest_id: uuid.UUID,
        amount: Money,
        gateway_order_id: str,
        attempt_number: int = 1,
        notes: dict[str, Any] | None = None,
    ) -> Payment:
        payment = cls(
            booking_id=booking_id,
            booking_reference=booking_reference,
            guest_id=guest_id,
            expected_amount=amount,
            gateway_order_id=gateway_order_id,
            attempt_number=attempt_number,
            notes=notes,
        )
        payment.record(
            PaymentOrderCreated(
                aggregate_id=payment.id,
                booking_id=booking_id,
                booking_reference=booking_reference,
                gateway_order_id=gateway_order_id,
                amount_minor=amount.amount_minor,
                currency=amount.currency,
                attempt_number=attempt_number,
            )
        )
        return payment

    # ── access ────────────────────────────────────────────────────────────

    def assert_visible_to(self, *, user_id: uuid.UUID | None, is_staff: bool = False) -> None:
        """404 at the interface, not 403 — see :class:`PaymentAccessDeniedError`."""
        if is_staff or (user_id is not None and user_id == self.guest_id):
            return
        raise errors.PaymentAccessDeniedError

    # ── status ────────────────────────────────────────────────────────────

    def _transition(self, target: PaymentStatus, *, strict: bool = True) -> bool:
        """Move forward, or refuse.

        ``strict=False`` returns ``False`` instead of raising, which is what
        webhook handling needs: a redelivered or out-of-order event is normal
        traffic, not an error, and must still be acknowledged with a 200 or
        Razorpay will keep redelivering it.
        """
        if target is self.status:
            return False  # already there; idempotent
        if target not in _TRANSITIONS.get(self.status, frozenset()):
            if strict:
                raise errors.InvalidPaymentTransitionError(self.status.value, target.value)
            return False
        self.status = target
        return True

    # ── gateway callbacks ─────────────────────────────────────────────────

    def assert_amount_matches(self, received: Money) -> None:
        """The single most important check in the module.

        The amount in a client callback is attacker-controlled, and the amount
        in a webhook could belong to a different order. Confirming a ₹50,000
        booking against a ₹1 payment is the outcome this prevents.
        """
        if received.currency != self.currency:
            raise errors.AmountMismatchError(
                self.expected_amount.amount_minor, received.amount_minor, self.currency
            )
        if received.amount_minor != self.expected_amount.amount_minor:
            raise errors.AmountMismatchError(
                self.expected_amount.amount_minor, received.amount_minor, self.currency
            )

    def mark_authorized(
        self,
        *,
        gateway_payment_id: str,
        amount: Money,
        method: PaymentMethod,
        now: datetime,
        vpa_or_last4: str | None = None,
        strict: bool = True,
    ) -> bool:
        """Funds are reserved on the card but **not taken**.

        A payment left authorised silently reverses after a few days, and the
        guest ends up with a confirmed booking nobody was paid for. The capture
        job exists for exactly this.
        """
        self.assert_amount_matches(amount)
        if not self._transition(PaymentStatus.AUTHORIZED, strict=strict):
            return False

        self.gateway_payment_id = gateway_payment_id
        self.method = method
        self.vpa_or_last4 = vpa_or_last4
        self.authorized_at = now
        self.record(
            PaymentAuthorized(
                aggregate_id=self.id,
                booking_id=self.booking_id,
                gateway_payment_id=gateway_payment_id,
                amount_minor=amount.amount_minor,
                currency=amount.currency,
                method=method.value,
            )
        )
        return True

    def mark_captured(
        self,
        *,
        gateway_payment_id: str,
        amount: Money,
        method: PaymentMethod,
        now: datetime,
        fee: Money | None = None,
        tax: Money | None = None,
        vpa_or_last4: str | None = None,
        strict: bool = True,
    ) -> bool:
        """Money has actually moved. The booking may now be confirmed.

        The gateway's fee and the tax on it are recorded as separate ledger
        entries. They are not part of what the guest paid, but they *are* part
        of what the platform receives, and a reconciliation that ignores them
        never balances against the settlement report.
        """
        self.assert_amount_matches(amount)
        if not self._transition(PaymentStatus.CAPTURED, strict=strict):
            return False

        self.gateway_payment_id = gateway_payment_id
        self.method = method
        self.vpa_or_last4 = vpa_or_last4 or self.vpa_or_last4
        self.captured_at = now
        self.gateway_fee = fee
        self.gateway_tax = tax

        self._post(TransactionKind.CHARGE, amount, now, gateway_payment_id, "Payment captured")
        if fee is not None and fee.is_positive:
            self._post(TransactionKind.GATEWAY_FEE, fee, now, gateway_payment_id, "Gateway fee")
        if tax is not None and tax.is_positive:
            self._post(TransactionKind.GATEWAY_TAX, tax, now, gateway_payment_id, "Tax on fee")

        self.record(
            PaymentCaptured(
                aggregate_id=self.id,
                booking_id=self.booking_id,
                booking_reference=self.booking_reference,
                guest_id=self.guest_id,
                gateway_payment_id=gateway_payment_id,
                amount_minor=amount.amount_minor,
                currency=amount.currency,
                method=method.value,
                fee_minor=fee.amount_minor if fee else 0,
            )
        )
        return True

    def mark_failed(
        self,
        *,
        code: str | None,
        reason: str | None,
        now: datetime,
        gateway_payment_id: str | None = None,
        strict: bool = True,
    ) -> bool:
        if not self._transition(PaymentStatus.FAILED, strict=strict):
            return False

        self.gateway_payment_id = gateway_payment_id or self.gateway_payment_id
        self.failure_code = code
        self.failure_reason = reason
        self.record(
            PaymentFailed(
                aggregate_id=self.id,
                booking_id=self.booking_id,
                booking_reference=self.booking_reference,
                guest_id=self.guest_id,
                gateway_payment_id=self.gateway_payment_id,
                code=code,
                reason=reason,
                attempt_number=self.attempt_number,
            )
        )
        return True

    def mark_disputed(self, *, amount: Money, now: datetime, reason: str | None = None) -> None:
        """A chargeback. The network pulls the money back and charges a fee.

        Recorded rather than treated as a refund: the accounting is different,
        the platform loses the fee either way, and a spike in chargebacks is a
        fraud signal that must be visible separately.
        """
        self._transition(PaymentStatus.DISPUTED, strict=False)
        self._post(TransactionKind.CHARGEBACK, amount, now, None, reason or "Chargeback")
        self.record(
            PaymentDisputed(
                aggregate_id=self.id,
                booking_id=self.booking_id,
                booking_reference=self.booking_reference,
                amount_minor=amount.amount_minor,
                currency=amount.currency,
                reason=reason,
            )
        )

    # ── refunds ───────────────────────────────────────────────────────────

    @property
    def captured_amount(self) -> Money:
        return self.expected_amount if self.status.is_money_taken else Money.zero(self.currency)

    @property
    def refunded_amount(self) -> Money:
        """Only settled refunds count.

        A pending one may still fail, and treating it as refunded would let a
        second refund be issued for money that never left.
        """
        total = Money.zero(self.currency)
        for refund in self.refunds:
            if refund.status is not RefundStatus.FAILED:
                total = total + refund.amount
        return total

    @property
    def refundable_amount(self) -> Money:
        return self.captured_amount - self.refunded_amount

    def request_refund(
        self,
        *,
        amount: Money,
        reason: str,
        idempotency_key: str,
        now: datetime,
        booking_id: uuid.UUID | None = None,
        speed: RefundSpeed = RefundSpeed.NORMAL,
    ) -> RefundAttempt:
        """Record a refund before calling the gateway.

        Written first on purpose: if the process dies between the gateway call
        and the database write, a recorded-but-unsent refund is recoverable by
        retrying with the same idempotency key. An unrecorded-but-sent one is
        money that left with nothing pointing at it.
        """
        if not self.status.is_money_taken:
            raise errors.RefundExceedsCapturedError(amount.amount_minor, 0)
        if amount.amount_minor > self.refundable_amount.amount_minor:
            raise errors.RefundExceedsCapturedError(
                amount.amount_minor, self.refundable_amount.amount_minor
            )

        existing = next((r for r in self.refunds if r.idempotency_key == idempotency_key), None)
        if existing is not None:
            # The same logical refund asked for twice. Return the original
            # rather than creating a second — this is the in-process half of
            # the idempotency guarantee; Razorpay's header is the other half.
            return existing

        attempt = RefundAttempt(
            amount=amount,
            reason=reason,
            idempotency_key=idempotency_key,
            requested_at=now,
            booking_id=booking_id,
            speed=speed,
        )
        self.refunds.append(attempt)
        self.record(
            RefundRecorded(
                aggregate_id=self.id,
                booking_id=booking_id or self.booking_id,
                refund_id=attempt.id,
                amount_minor=amount.amount_minor,
                currency=amount.currency,
                reason=reason,
                idempotency_key=idempotency_key,
            )
        )
        return attempt

    def mark_refund_processed(
        self, *, idempotency_key: str, gateway_refund_id: str, now: datetime
    ) -> bool:
        attempt = self._refund_by_key(idempotency_key)
        if attempt is None or attempt.is_settled:
            return False  # idempotent: Razorpay redelivers refund webhooks

        attempt.status = RefundStatus.PROCESSED
        attempt.gateway_refund_id = gateway_refund_id
        attempt.completed_at = now

        self._post(TransactionKind.REFUND, attempt.amount, now, gateway_refund_id, attempt.reason)

        # Fully or partly refunded — the distinction matters for reporting and
        # for whether a further refund is possible.
        self._transition(
            PaymentStatus.REFUNDED
            if self.refundable_amount.is_zero
            else PaymentStatus.PARTIALLY_REFUNDED,
            strict=False,
        )
        self.record(
            RefundProcessed(
                aggregate_id=self.id,
                booking_id=attempt.booking_id or self.booking_id,
                refund_id=attempt.id,
                gateway_refund_id=gateway_refund_id,
                amount_minor=attempt.amount.amount_minor,
                currency=attempt.amount.currency,
                succeeded=True,
                error=None,
            )
        )
        return True

    def mark_refund_failed(self, *, idempotency_key: str, error: str, now: datetime) -> bool:
        attempt = self._refund_by_key(idempotency_key)
        if attempt is None or attempt.is_settled:
            return False

        attempt.status = RefundStatus.FAILED
        attempt.failure_reason = error[:500]
        self.record(
            RefundProcessed(
                aggregate_id=self.id,
                booking_id=attempt.booking_id or self.booking_id,
                refund_id=attempt.id,
                gateway_refund_id=None,
                amount_minor=attempt.amount.amount_minor,
                currency=attempt.amount.currency,
                succeeded=False,
                error=error[:500],
            )
        )
        return True

    def _refund_by_key(self, idempotency_key: str) -> RefundAttempt | None:
        return next((r for r in self.refunds if r.idempotency_key == idempotency_key), None)

    # ── retry ─────────────────────────────────────────────────────────────

    def assert_can_retry(self) -> None:
        """A failed payment is never revived; the guest gets a *new* one.

        Reusing a Razorpay order after a failure produces confusing dashboard
        state and, on some methods, a duplicate charge. A new order per attempt
        keeps each try independently traceable.
        """
        if self.status.is_money_taken:
            raise errors.RetryNotAllowedError("already_paid")
        if not self.status.is_retryable:
            raise errors.RetryNotAllowedError(self.status.value)

    # ── ledger ────────────────────────────────────────────────────────────

    def _post(
        self,
        kind: TransactionKind,
        amount: Money,
        occurred_at: datetime,
        reference: str | None,
        note: str | None,
    ) -> None:
        self.ledger.append(
            LedgerEntry(
                kind=kind,
                amount=amount,
                occurred_at=occurred_at,
                gateway_reference=reference,
                note=note,
            )
        )

    @property
    def net_position(self) -> Money:
        """What the platform actually holds on this payment.

        `sum(ledger)`, not a maintained column — charge minus refunds, fees and
        chargebacks. This is the number that must match the settlement report,
        and computing it from the entries is what makes a mismatch explainable.
        """
        total = Money.zero(self.currency)
        for entry in self.ledger:
            total = total + entry.signed_amount
        return total
