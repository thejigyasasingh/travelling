"""Scheduled booking jobs.

``expire_holds`` is the most operationally important job in the system. If it
stops, inventory leaks silently: abandoned checkouts keep holding rooms,
properties go dark on their busiest dates, and nothing errors anywhere. It is
therefore on the ``critical`` queue, alerted on, and safe to run concurrently.

All three jobs use ``FOR UPDATE SKIP LOCKED`` in their queries, so running two
workers doubles throughput instead of double-processing.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.infrastructure.queue.async_bridge import run_async
from app.infrastructure.queue.celery_app import QueueName, celery_app
from app.modules.booking.infrastructure.unit_of_work import BookingUow
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

SYSTEM = Actor.system()

#: One batch per run. Small enough that a run finishes well inside its
#: schedule, large enough to keep up with a spike — at 200/minute the expiry
#: job clears a Diwali-scale abandoned-cart burst in a couple of minutes.
EXPIRY_BATCH = 200
STAY_BATCH = 500


async def _run(job: str, batch: int) -> int:
    """Build a container, run one job, commit."""
    from app.container import get_container

    container = await get_container()
    async with container.database.write_session() as session:
        uow = BookingUow(session)

        if job == "expire":
            from app.modules.booking.application.use_cases.lifecycle import (
                ExpireHoldsUseCase,
            )

            use_case: Any = ExpireHoldsUseCase(
                bookings=uow.bookings, inventory=uow.inventory, clock=container.clock
            )
        elif job == "start":
            from app.modules.booking.application.use_cases.lifecycle import (
                StartStaysUseCase,
            )

            use_case = StartStaysUseCase(bookings=uow.bookings, clock=container.clock)
        else:
            from app.modules.booking.application.use_cases.lifecycle import (
                CompleteStaysUseCase,
                FlatCommission,
            )

            use_case = CompleteStaysUseCase(
                bookings=uow.bookings,
                inventory=uow.inventory,
                commission=FlatCommission(),
                clock=container.clock,
            )

        count = await use_case.execute(batch, SYSTEM)
        await uow.flush()
        return int(count)


@celery_app.task(
    name="app.modules.booking.tasks.expire_holds",
    queue=QueueName.CRITICAL,
    # No autoretry: Beat re-runs this every minute anyway, and a retry storm
    # on top of a minute-by-minute schedule only makes an outage worse.
    autoretry_for=(),
    ignore_result=True,
)
def expire_holds() -> int:  # pragma: no cover — sync bridge only; `_run` is the logic
    """Release inventory from lapsed holds. Every minute.

    Runs on the critical queue so it can never queue behind image processing —
    a hold released ten minutes late is a room that could have been sold.
    """
    released = run_async(_run("expire", EXPIRY_BATCH))
    if released:
        logger.info("expired_holds_released", count=released)
    return released


@celery_app.task(
    name="app.modules.booking.tasks.start_stays",
    queue=QueueName.SCHEDULED,
    ignore_result=True,
)
def start_stays() -> int:  # pragma: no cover
    """Move today's arrivals to `in_stay`. Daily, after local check-in time."""
    return run_async(_run("start", STAY_BATCH))


@celery_app.task(
    name="app.modules.booking.tasks.complete_stays",
    queue=QueueName.SCHEDULED,
    ignore_result=True,
)
def complete_stays() -> int:  # pragma: no cover
    """Close out departures and release vendor payouts. Daily, after checkout.

    Payout is held until here rather than paid on confirmation: paying earlier
    would mean clawing money back on every cancellation, and by then it is
    usually spent.
    """
    return run_async(_run("complete", STAY_BATCH))


#: Beat schedule. Registered by the worker bootstrap.
BEAT_SCHEDULE: dict[str, dict[str, Any]] = {
    "expire-booking-holds": {
        "task": "app.modules.booking.tasks.expire_holds",
        "schedule": 60.0,
        # A run that overruns its minute must not stack: expire_on_next_run
        # keeps at most one queued.
        "options": {"queue": QueueName.CRITICAL, "expires": 55},
    },
    "start-stays": {
        "task": "app.modules.booking.tasks.start_stays",
        # 09:00 IST — after the earliest realistic check-in, before anyone
        # looks at a dashboard.
        "schedule": {"hour": 3, "minute": 30},  # 03:30 UTC
        "options": {"queue": QueueName.SCHEDULED},
    },
    "complete-stays": {
        "task": "app.modules.booking.tasks.complete_stays",
        "schedule": {"hour": 7, "minute": 0},  # 12:30 IST, after checkout
        "options": {"queue": QueueName.SCHEDULED},
    },
}
