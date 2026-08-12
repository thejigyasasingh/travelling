"""The background jobs that move money.

Three of them, and until now none had a single line of coverage:

* ``_execute_refund`` — returns a guest's money after a cancellation;
* ``_capture`` — takes funds that were only authorised, before the
  authorisation reverses and a confirmed booking goes unpaid;
* ``_reconcile`` — settles a payment whose webhook never arrived.

They are simultaneously the code most likely to move money incorrectly and the
least likely to be noticed doing it. None of them runs on a request; nobody
watches their output; a failure is a warning in a worker log. One of them
carried `# pragma: no cover — exercised by an integration test` and no such
test existed.

**What is real and what is not.** Postgres, the repositories, the unit of work,
the use cases and the container are all real. Only the Razorpay HTTP client is
replaced — by a fake that records what it was asked to do and can be told to
fail. Everything worth getting wrong is on this side of that line.

The fake also refuses a refund larger than the payment and honours the
idempotency key, because a fake that always says yes turns every
"do-we-double-refund" test into a tautology.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text

from .conftest import Actor, Listing, seed_booking

pytestmark = pytest.mark.integration


# ══════════════════════════════════════════════════════════════════════════
# A gateway that behaves like one
# ══════════════════════════════════════════════════════════════════════════


@dataclass
class FakeGateway:
    """Razorpay, minus the network.

    Models the three behaviours the code under test actually depends on:
    idempotency keys deduplicate, refunds cannot exceed the payment, and
    anything can be made to fail.
    """

    payments: dict[str, Any] = field(default_factory=dict)
    refunds_by_key: dict[str, Any] = field(default_factory=dict)
    refund_calls: list[dict[str, Any]] = field(default_factory=list)
    capture_calls: list[str] = field(default_factory=list)
    fetch_calls: list[str] = field(default_factory=list)
    fail_with: Exception | None = None

    def register(
        self,
        payment_id: str,
        *,
        amount_minor: int,
        status: str = "captured",
        captured: bool = True,
        order_id: str | None = None,
    ) -> None:
        self.payments[payment_id] = {
            "amount_minor": amount_minor,
            "status": status,
            "captured": captured,
            "order_id": order_id,
            "refunded_minor": 0,
        }

    # ── the protocol ──────────────────────────────────────────────────────

    async def create_order(self, **kwargs: Any) -> Any:  # pragma: no cover — unused here
        raise NotImplementedError

    async def fetch_payment(self, payment_id: str) -> Any:
        self.fetch_calls.append(payment_id)
        if self.fail_with:
            raise self.fail_with
        return self._as_gateway_payment(payment_id)

    async def capture(self, payment_id: str, amount: Any) -> Any:
        self.capture_calls.append(payment_id)
        if self.fail_with:
            raise self.fail_with
        record = self._known(payment_id)
        record["status"] = "captured"
        record["captured"] = True
        return self._as_gateway_payment(payment_id)

    async def refund(
        self,
        *,
        payment_id: str,
        amount: Any,
        idempotency_key: str,
        notes: dict[str, str] | None = None,
        speed: Any = None,
    ) -> Any:
        from app.modules.payment.application.ports import GatewayRefund

        # **The** thing a fake gateway must get right. Razorpay deduplicates on
        # this header; a fake that ignores it would let a broken retry look
        # correct here and refund twice in production.
        if idempotency_key in self.refunds_by_key:
            return self.refunds_by_key[idempotency_key]

        self.refund_calls.append(
            {
                "payment_id": payment_id,
                "amount_minor": amount.amount_minor,
                "idempotency_key": idempotency_key,
            }
        )
        if self.fail_with:
            raise self.fail_with

        record = self._known(payment_id)
        remaining = record["amount_minor"] - record["refunded_minor"]
        if amount.amount_minor > remaining:
            msg = f"refund {amount.amount_minor} exceeds refundable {remaining}"
            raise ValueError(msg)
        record["refunded_minor"] += amount.amount_minor

        refund = GatewayRefund(
            id=f"rfnd_{uuid.uuid4().hex[:14]}",
            payment_id=payment_id,
            amount=amount,
            status="processed",
            speed="normal",
        )
        self.refunds_by_key[idempotency_key] = refund
        return refund

    def _known(self, payment_id: str) -> dict[str, Any]:
        """Tolerate payments this test did not create.

        `_capture` and `_reconcile` are **batch** jobs: they scan the whole
        table and will always find rows left by earlier tests, because the
        suite isolates by unique data rather than by rolling back. A fake that
        raised `KeyError` on those would fail every batch test for a reason
        that has nothing to do with the code under test.

        So unknown ids are registered on sight. Every assertion below is about
        a *named* payment, never a count, for the same reason.
        """
        if payment_id not in self.payments:
            self.register(payment_id, amount_minor=1_116_000, status="captured")
        return self.payments[payment_id]

    def _as_gateway_payment(self, payment_id: str) -> Any:
        from app.core.types.money import Money
        from app.modules.payment.application.ports import GatewayPayment
        from app.modules.payment.domain.value_objects import PaymentMethod

        record = self._known(payment_id)
        return GatewayPayment(
            id=payment_id,
            order_id=record["order_id"],
            amount=Money(amount_minor=record["amount_minor"], currency="INR"),
            status=record["status"],
            method=PaymentMethod.UPI,
            captured=record["captured"],
        )


@pytest.fixture
async def gateway(api_client: Any) -> Any:
    """Install the fake on the live container.

    The tasks resolve `container.payment_gateway` themselves, three call frames
    down, so this has to patch the singleton the running app built rather than
    construct a second one. Payments are off in the suite, so the real value is
    `None` — which is also what makes `_gateway_uow` raise, and one of the
    tests below relies on that.
    """
    from app.container import get_container

    container = await get_container()
    fake = FakeGateway()
    original = container.payment_gateway
    container.payment_gateway = fake  # type: ignore[assignment]
    try:
        yield fake
    finally:
        container.payment_gateway = original


# ══════════════════════════════════════════════════════════════════════════
# Seeding
# ══════════════════════════════════════════════════════════════════════════


async def seed_payment(
    db: Any,
    *,
    booking_id: uuid.UUID,
    booking_reference: str,
    guest_id: uuid.UUID,
    amount_minor: int,
    status: str,
    gateway_payment_id: str | None = None,
    authorized_at: datetime | None = None,
) -> uuid.UUID:
    """A payment row in a given state.

    Inserted directly rather than driven through checkout: these jobs exist for
    payments that are *stuck*, and the API has no route that leaves one
    authorised-but-uncaptured on purpose.
    """
    payment_id = uuid.uuid4()
    await db.execute(
        text(
            """
            INSERT INTO payments
                (id, booking_id, booking_reference, guest_id, gateway,
                 gateway_order_id, gateway_payment_id, status, method,
                 expected_amount_minor, currency, attempt_number,
                 authorized_at, notes, version, created_at, updated_at)
            VALUES
                (:id, :booking_id, :reference, :guest_id, 'razorpay',
                 :order_id, :gateway_payment_id, :status, 'upi',
                 :amount, 'INR', 1, :authorized_at, '{}'::jsonb, 1,
                 now() - interval '2 days', now())
            """
        ),
        {
            "id": payment_id,
            "booking_id": booking_id,
            "reference": booking_reference,
            "guest_id": guest_id,
            "order_id": f"order_{uuid.uuid4().hex[:14]}",
            "gateway_payment_id": gateway_payment_id,
            "status": status,
            "amount": amount_minor,
            "authorized_at": authorized_at,
        },
    )
    await db.commit()
    return payment_id


@dataclass
class Paid:
    booking_id: uuid.UUID
    reference: str
    payment_id: uuid.UUID
    gateway_payment_id: str
    amount_minor: int


async def a_paid_booking(
    db: Any,
    *,
    listing: Listing,
    guest: Actor,
    gateway: FakeGateway,
    status: str = "captured",
    booking_status: str = "confirmed",
    authorized_at: datetime | None = None,
) -> Paid:
    """A confirmed booking with a payment row against it.

    The amount is the seeded booking's fixed total (see `seed_booking`, which
    has to satisfy `ck_bookings_total_is_sum_of_parts`), so the payment matches
    what the booking says is owed — a mismatch would be rejected by the use
    case for the wrong reason and make these tests prove nothing.
    """
    booking_id = await seed_booking(db, listing=listing, guest_id=guest.id, status=booking_status)
    row = (
        await db.execute(
            text("SELECT reference, total_minor FROM bookings WHERE id = :id"),
            {"id": booking_id},
        )
    ).one()

    gateway_payment_id = f"pay_{uuid.uuid4().hex[:18]}"
    payment_id = await seed_payment(
        db,
        booking_id=booking_id,
        booking_reference=row.reference,
        guest_id=guest.id,
        amount_minor=row.total_minor,
        status=status,
        gateway_payment_id=gateway_payment_id,
        authorized_at=authorized_at,
    )
    gateway.register(
        gateway_payment_id,
        amount_minor=row.total_minor,
        status=status,
        captured=status == "captured",
    )
    return Paid(
        booking_id=booking_id,
        reference=row.reference,
        payment_id=payment_id,
        gateway_payment_id=gateway_payment_id,
        amount_minor=row.total_minor,
    )


async def payment_status(db: Any, payment_id: uuid.UUID) -> str:
    return str(
        (
            await db.execute(text("SELECT status FROM payments WHERE id = :id"), {"id": payment_id})
        ).scalar_one()
    )


# ══════════════════════════════════════════════════════════════════════════
# Refunds
# ══════════════════════════════════════════════════════════════════════════


async def test_a_refund_reaches_the_gateway(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    """The job's entire purpose, and it had never been run by a test."""
    from app.modules.payment.infrastructure.tasks import _execute_refund

    paid = await a_paid_booking(db, listing=listing, guest=guest, gateway=gateway)

    status = await _execute_refund(
        {"booking_id": str(paid.booking_id), "amount_minor": 450_000, "reason": "cancelled"}
    )

    # The returned status is the *payment's* state afterwards, not the
    # refund's: a partial refund leaves the payment `partially_refunded`, and a
    # full one leaves it `refunded`. Both mean the money moved.
    assert status in ("refunded", "partially_refunded", "processed", "pending"), status
    assert len(gateway.refund_calls) == 1
    assert gateway.refund_calls[0]["amount_minor"] == 450_000


async def test_a_refund_is_for_the_amount_booking_decided(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    """Booking computes the amount from its own cancellation policy; payments
    move exactly that. A job that refunded the full total regardless would be
    invisible until finance reconciled the month."""
    from app.modules.payment.infrastructure.tasks import _execute_refund

    paid = await a_paid_booking(db, listing=listing, guest=guest, gateway=gateway)

    await _execute_refund(
        {"booking_id": str(paid.booking_id), "amount_minor": 123_400, "reason": "partial"}
    )

    assert gateway.refund_calls[0]["amount_minor"] == 123_400


async def test_a_retried_refund_does_not_pay_twice(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    """**The** money test.

    The task retries with backoff, the broker redelivers at least once, and a
    worker can die between the gateway call and the commit. Any of those runs
    this twice. The idempotency key — derived from the booking, sent to
    Razorpay as a header — is what makes the second run a no-op.
    """
    from app.modules.payment.infrastructure.tasks import _execute_refund

    paid = await a_paid_booking(db, listing=listing, guest=guest, gateway=gateway)
    payload = {
        "booking_id": str(paid.booking_id),
        "amount_minor": 450_000,
        "reason": "cancelled",
    }

    await _execute_refund(payload)
    await _execute_refund(payload)

    total = gateway.payments[paid.gateway_payment_id]["refunded_minor"]
    assert total == 450_000, f"refunded {total} across two runs"


async def test_the_idempotency_key_is_derived_from_the_booking(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    """The guarantee above only holds if the key is *derived*, not generated.

    A `uuid4()` per attempt would be a different key each time, and Razorpay
    would happily refund again — the exact failure the key exists to prevent,
    and one that would still pass a naive "was it called once" assertion,
    because our own guard would mask it in a single process.

    `refund-{booking_id}` is stable across processes, across restarts, and
    across a queue redelivery three days later.
    """
    from app.modules.payment.infrastructure.tasks import _execute_refund

    paid = await a_paid_booking(db, listing=listing, guest=guest, gateway=gateway)

    await _execute_refund({"booking_id": str(paid.booking_id), "amount_minor": 450_000})

    assert gateway.refund_calls[0]["idempotency_key"] == f"refund-{paid.booking_id}"


async def test_our_own_guard_stops_a_second_call_before_the_gateway(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    """Two layers, and this is the inner one.

    The gateway deduplicates on the header — that is the cross-process
    backstop. But a repeat attempt does not even reach it: the recorded refund
    against `(payment, key)` short-circuits first. Worth pinning separately,
    because it is what keeps a retry storm from becoming a rate-limit problem
    at Razorpay rather than a correctness one here.
    """
    from app.modules.payment.infrastructure.tasks import _execute_refund

    paid = await a_paid_booking(db, listing=listing, guest=guest, gateway=gateway)
    payload = {"booking_id": str(paid.booking_id), "amount_minor": 450_000}

    await _execute_refund(payload)
    # Forget everything the gateway knows, so only *our* guard can stop it.
    gateway.refunds_by_key.clear()
    await _execute_refund(payload)

    assert len(gateway.refund_calls) == 1, "the second attempt reached the gateway"


async def test_a_cancelled_booking_that_was_never_paid_settles(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    """A free cancellation of an unpaid hold. There is nothing to return, and
    the booking must be told so — otherwise its refund state sits `pending`
    forever and shows in the guest's trips as money on its way."""
    from app.modules.payment.infrastructure.tasks import _execute_refund

    booking_id = await seed_booking(db, listing=listing, guest_id=guest.id, status="cancelled")

    status = await _execute_refund({"booking_id": str(booking_id), "amount_minor": 0})

    assert status == "no_payment"
    assert gateway.refund_calls == []


async def test_a_gateway_outage_raises_so_the_task_retries(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    """Swallowing this would lose the refund silently.

    The task's whole retry policy — backoff, five attempts, visibly failed
    afterwards — depends on the exception escaping. A refund that gives up
    quietly is a chargeback three weeks later.
    """
    from app.modules.payment.infrastructure.tasks import _execute_refund

    paid = await a_paid_booking(db, listing=listing, guest=guest, gateway=gateway)
    gateway.fail_with = ConnectionError("razorpay unreachable")

    with pytest.raises(Exception, match="unreachable"):
        await _execute_refund({"booking_id": str(paid.booking_id), "amount_minor": 450_000})


async def test_a_worker_with_no_gateway_refuses_to_run(
    db: Any, listing: Listing, guest: Actor
) -> None:
    """**The** silent-failure guard.

    A deployment with payments unconfigured must fail loudly here. Skipping
    refunds quietly is money the guest never gets back, with no error anywhere
    to say so — note this test takes no `gateway` fixture, so the container's
    value is the real `None`.
    """
    from app.modules.payment.infrastructure.tasks import _execute_refund

    booking_id = await seed_booking(db, listing=listing, guest_id=guest.id, status="cancelled")

    with pytest.raises(RuntimeError, match="no gateway is configured"):
        await _execute_refund({"booking_id": str(booking_id), "amount_minor": 450_000})


# ══════════════════════════════════════════════════════════════════════════
# Capture
# ══════════════════════════════════════════════════════════════════════════


async def test_a_stale_authorization_is_captured(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    """An authorisation reverses after a few days if nobody captures it.

    The result is a confirmed booking the host will honour and nobody was paid
    for — and it is completely silent, because from the guest's side the money
    simply reappears.
    """
    from app.modules.payment.infrastructure.tasks import _capture

    paid = await a_paid_booking(
        db,
        listing=listing,
        guest=guest,
        gateway=gateway,
        status="authorized",
        authorized_at=datetime.now(UTC) - timedelta(days=3),
    )

    await _capture(100)

    assert paid.gateway_payment_id in gateway.capture_calls
    assert await payment_status(db, paid.payment_id) == "captured"


async def test_a_fresh_authorization_is_left_alone(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    """Capturing immediately would defeat the point of authorising.

    The window exists so a booking can still be cancelled without a refund
    round trip; a job that grabbed everything the moment it appeared would
    charge guests for holds they abandoned.
    """
    from app.modules.payment.infrastructure.tasks import _capture

    paid = await a_paid_booking(
        db,
        listing=listing,
        guest=guest,
        gateway=gateway,
        status="authorized",
        authorized_at=datetime.now(UTC),
    )

    await _capture(100)

    assert paid.gateway_payment_id not in gateway.capture_calls
    assert await payment_status(db, paid.payment_id) == "authorized"


async def test_capture_ignores_payments_that_are_already_captured(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    """Re-capturing is an error at the gateway, and the job runs hourly."""
    from app.modules.payment.infrastructure.tasks import _capture

    paid = await a_paid_booking(db, listing=listing, guest=guest, gateway=gateway)

    await _capture(100)

    assert paid.gateway_payment_id not in gateway.capture_calls


# ══════════════════════════════════════════════════════════════════════════
# Reconciliation
# ══════════════════════════════════════════════════════════════════════════


async def test_reconciliation_asks_the_gateway_about_stuck_payments(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    """The webhook that never arrived.

    Without this the guest has paid, the money is gone, and their booking still
    says "payment pending" until someone opens a support ticket. The gateway is
    the source of truth; our row is a cache of it.
    """
    from app.modules.payment.infrastructure.tasks import _reconcile

    paid = await a_paid_booking(db, listing=listing, guest=guest, gateway=gateway, status="pending")
    # The gateway knows better than we do: it was captured all along.
    gateway.payments[paid.gateway_payment_id]["status"] = "captured"
    gateway.payments[paid.gateway_payment_id]["captured"] = True

    await _reconcile(100)

    assert paid.gateway_payment_id in gateway.fetch_calls


async def test_reconciliation_settles_the_row_from_the_gateway(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    from app.modules.payment.infrastructure.tasks import _reconcile

    paid = await a_paid_booking(db, listing=listing, guest=guest, gateway=gateway, status="pending")
    gateway.payments[paid.gateway_payment_id]["status"] = "captured"
    gateway.payments[paid.gateway_payment_id]["captured"] = True

    await _reconcile(100)

    assert await payment_status(db, paid.payment_id) == "captured"


async def test_reconciliation_is_safe_to_run_with_nothing_to_do(
    gateway: FakeGateway,
) -> None:
    """It runs every five minutes forever, and almost always finds nothing."""
    from app.modules.payment.infrastructure.tasks import _reconcile

    assert await _reconcile(100) >= 0


async def test_a_gateway_outage_during_reconciliation_leaves_the_row_alone(
    db: Any, listing: Listing, guest: Actor, gateway: FakeGateway
) -> None:
    """Reconciliation swallows per-payment failures, and should.

    Note the deliberate asymmetry with `_execute_refund`, which re-raises: that
    is a single-item task whose whole retry policy depends on the exception
    escaping. This is a **batch** job over every unsettled payment, re-run
    every five minutes. One unreachable payment must not abandon the other
    ninety-nine, so the error is logged per row and the batch continues.

    What must hold either way is that a failed *read* never becomes a write.
    Recording "unknown" here would destroy the one fact we had.
    """
    from app.modules.payment.infrastructure.tasks import _reconcile

    paid = await a_paid_booking(db, listing=listing, guest=guest, gateway=gateway, status="pending")
    gateway.fail_with = ConnectionError("razorpay unreachable")

    resolved = await _reconcile(100)

    assert resolved == 0, "a failed fetch was counted as resolved"
    assert paid.gateway_payment_id in gateway.fetch_calls, "the payment was never attempted"
    assert await payment_status(db, paid.payment_id) == "pending"
