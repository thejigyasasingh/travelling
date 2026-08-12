"""Scheduled and event-driven payment jobs.

These are the safety nets. Everything here exists because the happy path is not
guaranteed to happen:

* ``execute_refund`` — booking decided a refund is owed; this actually moves the
  money. Driven by ``booking.refund.requested`` rather than called inline, so a
  gateway outage delays a refund instead of failing a cancellation.
* ``reconcile_payments`` — a webhook that never arrived. Without this, a guest
  who paid waits for support to notice.
* ``capture_authorized`` — an authorisation reverses after a few days if it is
  not captured, leaving a confirmed booking nobody was paid for.
* ``purge_webhook_payloads`` — retention. Payloads carry guest contact details.

All of them run on the **critical** queue and all of them are safe to run
concurrently: the queries take ``FOR UPDATE SKIP LOCKED``, and the refund path
is idempotent through a key derived from the booking id.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from app.core.logging import get_logger
from app.infrastructure.queue.async_bridge import run_async
from app.infrastructure.queue.celery_app import QueueName, celery_app
from app.modules.payment.application.dto import RefundInput
from app.modules.payment.infrastructure.unit_of_work import PaymentUow
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

SYSTEM = Actor.system()

#: One batch per run. Reconciliation touches the gateway once per payment, so
#: the batch is sized to finish inside its schedule even at the slow end of
#: Razorpay's latency.
RECONCILE_BATCH = 100
CAPTURE_BATCH = 100


async def _gateway_uow() -> tuple[Any, Any]:
    """Container plus a check that payments are actually configured.

    Returns the container, or raises. A worker with no gateway must fail
    loudly: silently skipping refunds is money the guest never gets back.
    """
    from app.container import get_container

    container = await get_container()
    if container.payment_gateway is None:
        msg = "Payment tasks are scheduled but no gateway is configured"
        raise RuntimeError(msg)
    return container, container.payment_gateway


# ══════════════════════════════════════════════════════════════════════════
# Refunds
# ══════════════════════════════════════════════════════════════════════════


async def _execute_refund(payload: dict[str, Any]) -> str:
    container, gateway = await _gateway_uow()

    booking_id = uuid.UUID(str(payload["booking_id"]))
    payment_id = payload.get("payment_id")

    async with container.database.write_session() as session:
        uow = PaymentUow(session)

        payment = (
            await uow.payments.get(uuid.UUID(str(payment_id)))
            if payment_id
            else await uow.payments.get_active_for_booking(booking_id)
        )
        if payment is None:
            # A cancelled booking that was never paid for. Nothing to return,
            # and the booking is told so its refund state settles rather than
            # sitting "pending" forever.
            await uow.bookings.record_refund_result(
                booking_id=booking_id, succeeded=True, gateway_refund_id="no-payment"
            )
            await uow.commit()
            logger.info("refund_skipped_no_payment", booking_id=str(booking_id))
            return "no_payment"

        from app.modules.payment.application.use_cases.refunds import IssueRefundUseCase

        use_case = IssueRefundUseCase(
            payments=uow.payments,
            bookings=uow.bookings,
            gateway=gateway,
            clock=container.clock,
        )
        result = await use_case.execute(
            RefundInput(
                payment_id=payment.id,
                amount_minor=int(payload["amount_minor"]),
                reason=str(payload.get("reason") or "requested_by_customer"),
                speed=container.settings.payment.default_refund_speed,
            ),
            SYSTEM,
        )
        await uow.commit()
        return result.status


@celery_app.task(
    name="app.modules.payment.tasks.execute_refund",
    queue=QueueName.CRITICAL,
    bind=True,
    # Retried with backoff, unlike the scheduled jobs: this one is not re-run by
    # Beat, so if it gives up the guest's money simply does not come back. The
    # idempotency key makes every retry safe.
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_backoff_max=3600,
    retry_jitter=True,
    max_retries=10,
    ignore_result=True,
)
def execute_refund(  # pragma: no cover — the sync bridge; body covered by test_money_jobs
    self: Any,
    *,
    event_id: str = "",
    aggregate_id: str = "",
    event_version: int = 1,
    payload: dict[str, Any] | None = None,
    # Tolerates fields the dispatcher gains later. Without it, adding one
    # breaks every message already sitting in the queue at deploy time — and
    # for this task those messages are refunds.
    **_: Any,
) -> str:
    """Move the money for a ``booking.refund.requested`` event.

    Idempotent twice over: our own unique ``(payment_id, idempotency_key)``
    stops a second attempt row, and the same key goes to Razorpay as a header
    so even a refund we never recorded is not issued twice.

    After ``max_retries`` this stays visibly failed rather than disappearing —
    a refund that silently gives up is a chargeback three weeks later.
    """
    data = dict(payload or {})
    data.setdefault("booking_id", aggregate_id)
    outcome = run_async(_execute_refund(data))
    logger.info(
        "refund_task_finished",
        booking_id=data.get("booking_id"),
        outcome=outcome,
        attempt=self.request.retries,
    )
    return outcome


# ══════════════════════════════════════════════════════════════════════════
# Reconciliation and capture
# ══════════════════════════════════════════════════════════════════════════


async def _reconcile(batch: int) -> int:
    container, gateway = await _gateway_uow()
    async with container.database.write_session() as session:
        uow = PaymentUow(session)

        from app.modules.payment.application.use_cases.refunds import (
            ReconcilePaymentsUseCase,
        )

        use_case = ReconcilePaymentsUseCase(
            payments=uow.payments,
            bookings=uow.bookings,
            gateway=gateway,
            clock=container.clock,
        )
        count = await use_case.execute(batch, SYSTEM)
        await uow.commit()
        return count


async def _capture(batch: int) -> int:
    container, gateway = await _gateway_uow()
    async with container.database.write_session() as session:
        uow = PaymentUow(session)

        from app.modules.payment.application.use_cases.refunds import (
            CaptureAuthorizedUseCase,
        )

        use_case = CaptureAuthorizedUseCase(
            payments=uow.payments,
            bookings=uow.bookings,
            gateway=gateway,
            clock=container.clock,
        )
        count = await use_case.execute(batch, SYSTEM)
        await uow.commit()
        return count


async def _purge_webhooks(retention_days: int) -> int:
    from app.container import get_container

    container = await get_container()
    async with container.database.write_session() as session:
        uow = PaymentUow(session)
        cutoff = container.clock.now() - timedelta(days=retention_days)
        deleted = await uow.events.purge_processed(before=cutoff)
        await session.commit()
        return deleted


@celery_app.task(
    name="app.modules.payment.tasks.reconcile_payments",
    queue=QueueName.CRITICAL,
    autoretry_for=(),  # Beat re-runs it; a retry storm on an outage helps nobody
    ignore_result=True,
)
def reconcile_payments() -> int:  # pragma: no cover
    """Ask the gateway about payments whose webhook never arrived.

    The single most important job in this module. Webhooks are delivered at
    least once, which occasionally means never — a misconfigured endpoint, an
    outage on either side, a deploy that returned 502 for five minutes. Without
    this, a guest who paid sits with an unconfirmed booking.
    """
    resolved = run_async(_reconcile(RECONCILE_BATCH))
    if resolved:
        logger.info("payments_reconciled", count=resolved)
    return resolved


@celery_app.task(
    name="app.modules.payment.tasks.capture_authorized",
    queue=QueueName.CRITICAL,
    autoretry_for=(),
    ignore_result=True,
)
def capture_authorized() -> int:  # pragma: no cover
    """Capture authorisations before Razorpay reverses them.

    A no-op when auto-capture is on, which is the default. It runs anyway: the
    setting can change, and an uncaptured authorisation reverses silently.
    """
    captured = run_async(_capture(CAPTURE_BATCH))
    if captured:
        logger.info("authorizations_captured", count=captured)
    return captured


@celery_app.task(
    name="app.modules.payment.tasks.purge_webhook_payloads",
    queue=QueueName.SCHEDULED,
    ignore_result=True,
)
def purge_webhook_payloads() -> int:  # pragma: no cover
    """Drop old webhook payloads.

    They are kept long enough to replay a mishandled delivery and no longer:
    they contain the guest's name, email and phone, and retention is the
    cheapest form of data protection there is.
    """
    from app.core.config import get_settings

    deleted = run_async(_purge_webhooks(get_settings().payment.webhook_retention_days))
    if deleted:
        logger.info("webhook_payloads_purged", count=deleted)
    return deleted


#: Beat schedule. Registered by the worker bootstrap.
BEAT_SCHEDULE: dict[str, dict[str, Any]] = {
    "reconcile-payments": {
        "task": "app.modules.payment.tasks.reconcile_payments",
        # Every 5 minutes. The use case only looks at payments older than 15,
        # so a webhook has plenty of time to arrive first and this rarely has
        # anything to do — which is exactly what a safety net should look like.
        "schedule": 300.0,
        "options": {"queue": QueueName.CRITICAL, "expires": 280},
    },
    "capture-authorized": {
        "task": "app.modules.payment.tasks.capture_authorized",
        "schedule": 3600.0,
        "options": {"queue": QueueName.CRITICAL, "expires": 3500},
    },
    "purge-webhook-payloads": {
        "task": "app.modules.payment.tasks.purge_webhook_payloads",
        "schedule": {"hour": 2, "minute": 15},  # 07:45 IST, off-peak
        "options": {"queue": QueueName.SCHEDULED},
    },
}
