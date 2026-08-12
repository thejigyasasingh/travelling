"""Webhook processing.

Webhooks are the **authoritative** payment path — the browser callback is a
convenience. Delivery is at-least-once, ordering is not guaranteed, and
Razorpay redelivers on any non-2xx. So the properties under test are:

* nothing happens before the signature checks out;
* a redelivered event has no second effect;
* an out-of-order event is ignored, not applied and not rejected;
* an unknown event type is acknowledged rather than erroring forever;
* a business condition we have already recorded still answers 200, because a
  handler that raises on normal traffic buries the real failures under retries.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.types.money import Money
from app.modules.payment.application.dto import WebhookInput
from app.modules.payment.application.ports import GatewayPayment
from app.modules.payment.application.use_cases.webhooks import ProcessWebhookUseCase
from app.modules.payment.domain.entities import Payment
from app.modules.payment.domain.signature import SignatureError
from app.modules.payment.domain.value_objects import PaymentMethod, PaymentStatus
from app.shared.application.use_case import Actor

pytestmark = pytest.mark.unit

INR = "INR"
NOW = datetime.now(UTC).replace(microsecond=0)
AMOUNT_MINOR = 45_000_00
ORDER_ID = "order_MkL9pQrStUvWxY"
PAYMENT_ID = "pay_MkL9pQrStUvWxZ"
SYSTEM = Actor.system()


class FixedClock:
    def now(self) -> datetime:
        return NOW


# ── fakes ─────────────────────────────────────────────────────────────────


@dataclass
class FakePaymentRepository:
    payments: dict[uuid.UUID, Payment] = field(default_factory=dict)

    async def get(self, payment_id: uuid.UUID) -> Payment | None:
        return self.payments.get(payment_id)

    async def get_by_order_id(self, order_id: str) -> Payment | None:
        return next((p for p in self.payments.values() if p.gateway_order_id == order_id), None)

    async def get_by_gateway_payment_id(self, gateway_payment_id: str) -> Payment | None:
        return next(
            (p for p in self.payments.values() if p.gateway_payment_id == gateway_payment_id),
            None,
        )

    async def get_active_for_booking(self, booking_id: uuid.UUID) -> Payment | None:
        return next((p for p in self.payments.values() if p.booking_id == booking_id), None)

    async def add(self, payment: Payment) -> None:
        self.payments[payment.id] = payment

    async def count_attempts(self, booking_id: uuid.UUID) -> int:
        return len([p for p in self.payments.values() if p.booking_id == booking_id])

    async def list_for_guest(self, guest_id: uuid.UUID, **_: Any) -> tuple[list[Payment], bool]:
        return [], False

    async def find_stale_authorized(self, **_: Any) -> list[Payment]:
        return []

    async def find_pending_reconciliation(self, **_: Any) -> list[Payment]:
        return []


@dataclass
class FakeBookings:
    """Records what payments asked booking to do, without a database.

    Confirmation is **idempotent here because it is idempotent there**: the real
    ``ConfirmBookingUseCase`` returns the existing view for an already-confirmed
    booking rather than issuing a second invoice number or a second
    confirmation email. A fake that re-confirmed on every call would let a test
    pass that production would fail, and vice versa.
    """

    confirmed: list[tuple[uuid.UUID, str, Money]] = field(default_factory=list)
    invoices_issued: list[uuid.UUID] = field(default_factory=list)
    refund_results: list[tuple[uuid.UUID, bool]] = field(default_factory=list)
    invoice_number: str | None = "RW/2026-27/000042"
    confirm_error: Exception | None = None

    async def snapshot(self, booking_id: uuid.UUID) -> None:
        return None

    async def confirm_paid(
        self, *, booking_id: uuid.UUID, payment_id: str, paid_amount: Money
    ) -> str | None:
        if self.confirm_error is not None:
            raise self.confirm_error
        self.confirmed.append((booking_id, payment_id, paid_amount))
        if booking_id not in self.invoices_issued:
            self.invoices_issued.append(booking_id)
        return self.invoice_number

    async def record_refund_result(
        self,
        *,
        booking_id: uuid.UUID,
        succeeded: bool,
        gateway_refund_id: str | None = None,
        error: str | None = None,
    ) -> None:
        self.refund_results.append((booking_id, succeeded))


@dataclass
class FakeEventStore:
    seen: set[str] = field(default_factory=set)
    processed: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)

    async def claim(
        self, *, event_id: str, event_type: str, payload: dict[str, Any], now: datetime
    ) -> bool:
        if event_id in self.seen:
            return False
        self.seen.add(event_id)
        return True

    async def mark_processed(self, event_id: str, *, now: datetime) -> None:
        self.processed.append(event_id)

    async def mark_failed(self, event_id: str, *, error: str, now: datetime) -> None:
        self.failed.append((event_id, error))

    async def find_unprocessed(self, *, limit: int = 100) -> list[dict[str, Any]]:
        return []


@dataclass
class FakeGateway:
    """Signature verification is the only part the webhook path uses."""

    valid_signature: str = "valid-signature"
    verified: list[bytes] = field(default_factory=list)

    def verify_webhook_signature(self, *, raw_body: bytes, signature: str) -> None:
        self.verified.append(raw_body)
        if signature != self.valid_signature:
            raise SignatureError("webhook")

    def verify_checkout_signature(self, **_: Any) -> None: ...

    async def create_order(self, **_: Any) -> Any: ...

    async def fetch_payment(self, payment_id: str) -> GatewayPayment: ...

    async def capture(self, payment_id: str, amount: Money) -> GatewayPayment: ...

    async def refund(self, **_: Any) -> Any: ...

    @property
    def public_key(self) -> str:
        return "rzp_test_key"


# ── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def payment() -> Payment:
    return Payment.create_order(
        booking_id=uuid.uuid4(),
        booking_reference="RW7QK4XM",
        guest_id=uuid.uuid4(),
        amount=Money(AMOUNT_MINOR, INR),
        gateway_order_id=ORDER_ID,
    )


@pytest.fixture
def use_case(payment: Payment) -> ProcessWebhookUseCase:
    repo = FakePaymentRepository({payment.id: payment})
    return ProcessWebhookUseCase(
        payments=repo,
        bookings=FakeBookings(),
        events=FakeEventStore(),
        gateway=FakeGateway(),
        clock=FixedClock(),
    )


def event(
    event_type: str = "payment.captured",
    *,
    amount: int = AMOUNT_MINOR,
    captured: bool = True,
    order_id: str | None = ORDER_ID,
    status: str = "captured",
) -> dict[str, Any]:
    return {
        "event": event_type,
        "payload": {
            "payment": {
                "entity": {
                    "id": PAYMENT_ID,
                    "order_id": order_id,
                    "amount": amount,
                    "currency": INR,
                    "status": status,
                    "method": "upi",
                    "vpa": "guest@okhdfcbank",
                    "captured": captured,
                    "fee": 900_00,
                    "tax": 162_00,
                }
            }
        },
    }


def delivery(
    payload: dict[str, Any], *, event_id: str = "evt_1", signature: str = "valid-signature"
) -> WebhookInput:
    return WebhookInput(
        raw_body=b'{"raw":"bytes"}', signature=signature, event_id=event_id, payload=payload
    )


# ══════════════════════════════════════════════════════════════════════════
# Signature
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_a_bad_signature_stops_everything(use_case: ProcessWebhookUseCase) -> None:
    """Nothing below the signature check runs. A forged ``payment.captured``
    would otherwise be a free booking."""
    with pytest.raises(SignatureError):
        await use_case.execute(delivery(event(), signature="forged"), SYSTEM)

    assert use_case.events.seen == set(), "the event must not even be claimed"
    assert use_case.bookings.confirmed == []


@pytest.mark.asyncio
async def test_the_raw_body_is_what_gets_verified(use_case: ProcessWebhookUseCase) -> None:
    """Not the parsed payload — re-serialised JSON produces a different HMAC."""
    await use_case.execute(delivery(event()), SYSTEM)
    assert use_case.gateway.verified == [b'{"raw":"bytes"}']


# ══════════════════════════════════════════════════════════════════════════
# The happy path
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_a_captured_event_confirms_the_booking(
    use_case: ProcessWebhookUseCase, payment: Payment
) -> None:
    result = await use_case.execute(delivery(event()), SYSTEM)

    assert payment.status is PaymentStatus.CAPTURED
    assert payment.method is PaymentMethod.UPI
    assert payment.vpa_or_last4 == "guest@okhdfcbank"
    assert len(use_case.bookings.confirmed) == 1
    assert result["payment_id"] == str(payment.id)
    assert use_case.events.processed == ["evt_1"]


@pytest.mark.asyncio
async def test_the_gateway_fee_and_tax_reach_the_ledger(
    use_case: ProcessWebhookUseCase, payment: Payment
) -> None:
    """Without them, reconciliation against the settlement report never
    balances."""
    await use_case.execute(delivery(event()), SYSTEM)
    kinds = [e.kind.value for e in payment.ledger]
    assert kinds == ["charge", "gateway_fee", "gateway_tax"]


# ══════════════════════════════════════════════════════════════════════════
# At-least-once delivery
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_a_redelivered_event_has_no_second_effect(
    use_case: ProcessWebhookUseCase, payment: Payment
) -> None:
    """Razorpay redelivers even after a 200. The claim is what makes the
    *effect* exactly-once."""
    await use_case.execute(delivery(event()), SYSTEM)
    result = await use_case.execute(delivery(event()), SYSTEM)

    assert result["status"] == "duplicate"
    # Not even asked a second time — the claim short-circuits before dispatch.
    assert len(use_case.bookings.confirmed) == 1
    assert len([e for e in payment.ledger if e.kind.value == "charge"]) == 1


@pytest.mark.asyncio
async def test_a_different_event_id_for_the_same_payment_is_still_safe(
    use_case: ProcessWebhookUseCase, payment: Payment
) -> None:
    """Dedupe is the first line, not the only one.

    A redelivery with a fresh event id gets past the claim, so the aggregate's
    forward-only transitions have to catch it — and they do: the second capture
    is a no-op, so no second ledger entry and no second confirmation.
    """
    await use_case.execute(delivery(event(), event_id="evt_1"), SYSTEM)
    await use_case.execute(delivery(event(), event_id="evt_2"), SYSTEM)

    assert len([e for e in payment.ledger if e.kind.value == "charge"]) == 1
    # Confirmation is *asked for* twice on purpose — that is what lets a
    # redelivery recover a confirmation that failed the first time. What must
    # not happen twice is the effect: one invoice, one confirmation email.
    assert use_case.bookings.invoices_issued == [payment.booking_id]


@pytest.mark.asyncio
async def test_an_out_of_order_authorized_event_is_ignored_not_rejected(
    use_case: ProcessWebhookUseCase, payment: Payment
) -> None:
    """``captured`` before ``authorized`` is routine. The late one must be
    acknowledged — rejecting it makes Razorpay redeliver it forever."""
    await use_case.execute(delivery(event("payment.captured"), event_id="evt_1"), SYSTEM)
    result = await use_case.execute(
        delivery(
            event("payment.authorized", captured=False, status="authorized"), event_id="evt_2"
        ),
        SYSTEM,
    )

    assert payment.status is PaymentStatus.CAPTURED
    assert "evt_2" in use_case.events.processed
    assert result["payment_id"] == str(payment.id)


# ══════════════════════════════════════════════════════════════════════════
# Things that must be acknowledged rather than retried forever
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_an_unhandled_event_type_is_acknowledged(
    use_case: ProcessWebhookUseCase,
) -> None:
    """Razorpay sends dozens of event types. Subscribing to one we do not act
    on must not produce an error every time it fires."""
    result = await use_case.execute(
        delivery({"event": "payment.downtime.started", "payload": {}}), SYSTEM
    )
    assert result["status"] == "ignored"
    assert use_case.events.processed == ["evt_1"]


@pytest.mark.asyncio
async def test_a_webhook_for_an_unknown_order_is_acknowledged(
    use_case: ProcessWebhookUseCase,
) -> None:
    """It may belong to another environment pointed at the same endpoint.
    Logged, acknowledged, not retried forever."""
    result = await use_case.execute(delivery(event(order_id="order_SomethingElse")), SYSTEM)
    assert result["status"] == "unknown_order"


@pytest.mark.asyncio
async def test_an_amount_mismatch_is_reported_but_not_retried(
    use_case: ProcessWebhookUseCase, payment: Payment
) -> None:
    """Either tampering or a bug in our own pricing. Both need a human, and
    neither is fixed by Razorpay sending the event again."""
    result = await use_case.execute(delivery(event(amount=100)), SYSTEM)

    assert result["status"] == "amount_mismatch"
    assert payment.status is PaymentStatus.CREATED
    assert use_case.bookings.confirmed == []
    assert use_case.events.processed == ["evt_1"]


@pytest.mark.asyncio
async def test_a_booking_that_cannot_be_confirmed_still_answers_ok(
    payment: Payment,
) -> None:
    """The expired-hold case: the money is captured but the rooms are gone.

    The payment stays captured — it truthfully did — and the reconciliation job
    raises it for refund. Erroring here would just make Razorpay redeliver it.
    """
    bookings = FakeBookings(confirm_error=RuntimeError("hold expired"))
    use_case = ProcessWebhookUseCase(
        payments=FakePaymentRepository({payment.id: payment}),
        bookings=bookings,
        events=FakeEventStore(),
        gateway=FakeGateway(),
        clock=FixedClock(),
    )

    result = await use_case.execute(delivery(event()), SYSTEM)

    assert result["status"] == "confirm_failed"
    assert payment.status is PaymentStatus.CAPTURED


# ══════════════════════════════════════════════════════════════════════════
# Refunds and disputes
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_a_refund_webhook_settles_the_matching_attempt(
    use_case: ProcessWebhookUseCase, payment: Payment
) -> None:
    """Razorpay echoes our notes back, which is how the refund is matched to
    the attempt we recorded before calling it."""
    await use_case.execute(delivery(event(), event_id="evt_1"), SYSTEM)
    key = f"refund-{payment.booking_id}"
    payment.request_refund(
        amount=Money(AMOUNT_MINOR, INR), reason="cancellation", idempotency_key=key, now=NOW
    )

    result = await use_case.execute(
        delivery(
            {
                "event": "refund.processed",
                "payload": {
                    "refund": {
                        "entity": {
                            "id": "rfnd_1",
                            "payment_id": PAYMENT_ID,
                            "amount": AMOUNT_MINOR,
                            "currency": INR,
                            "notes": {"idempotency_key": key},
                        }
                    }
                },
            },
            event_id="evt_refund",
        ),
        SYSTEM,
    )

    assert result["status"] == "refund_recorded"
    assert payment.status is PaymentStatus.REFUNDED
    assert use_case.bookings.refund_results == [(payment.booking_id, True)]


@pytest.mark.asyncio
async def test_a_dispute_is_recorded_and_the_ledger_reflects_it(
    use_case: ProcessWebhookUseCase, payment: Payment
) -> None:
    """A chargeback has a response deadline and an evidence process a human
    runs. What matters here is that the ledger tells the truth."""
    await use_case.execute(delivery(event(), event_id="evt_1"), SYSTEM)

    result = await use_case.execute(
        delivery(
            {
                "event": "payment.dispute.created",
                "payload": {
                    "dispute": {
                        "entity": {
                            "payment_id": PAYMENT_ID,
                            "amount": AMOUNT_MINOR,
                            "currency": INR,
                            "reason_code": "fraud",
                        }
                    }
                },
            },
            event_id="evt_dispute",
        ),
        SYSTEM,
    )

    assert result["status"] == "dispute_recorded"
    assert payment.status is PaymentStatus.DISPUTED
    assert any(e.kind.value == "chargeback" for e in payment.ledger)
