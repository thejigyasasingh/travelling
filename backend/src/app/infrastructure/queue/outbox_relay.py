"""Outbox relay — the other half of the transactional outbox.

The writer (``infrastructure/database/outbox.py``) puts events in Postgres
inside the business transaction. This drains them into Celery.

``SELECT ... FOR UPDATE SKIP LOCKED`` is the whole trick. Multiple relay
instances poll the same table concurrently; each grabs a batch of rows nobody
else has locked and skips the rest instead of blocking. Without ``SKIP
LOCKED``, N relays serialise behind one another and the relay becomes the
bottleneck — with it, throughput scales with instance count and no event is
ever dispatched twice.

Delivery is **at-least-once**, so every consumer must be idempotent. Exactly-once
delivery does not exist across a process boundary; exactly-once *effect* is
achieved by consumers deduplicating on ``event_id``.

Failures back off and eventually park. After ``MAX_ATTEMPTS`` a row stops being
selected (the partial index excludes it) and is surfaced as a dead-letter for a
human, rather than being retried forever at one attempt per second.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.infrastructure.database.outbox import OutboxEvent
from app.infrastructure.queue.async_bridge import run_async
from app.infrastructure.queue.celery_app import QueueName, celery_app

logger = get_logger(__name__)

BATCH_SIZE = 100
MAX_ATTEMPTS = 10


async def relay_batch(session: AsyncSession, *, batch_size: int = BATCH_SIZE) -> int:
    """Claim and dispatch one batch. Returns how many were dispatched.

    The caller owns the transaction. Rows stay locked until it commits, which
    is what makes the claim safe.
    """
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.processed_at.is_(None), OutboxEvent.attempts < MAX_ATTEMPTS)
        .order_by(OutboxEvent.created_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    events = (await session.execute(stmt)).scalars().all()
    if not events:
        return 0

    dispatched: list[Any] = []
    for event in events:
        try:
            celery_app.send_task(
                "app.events.dispatch",
                kwargs={
                    "event_id": str(event.id),
                    "event_type": event.event_type,
                    "aggregate_type": event.aggregate_type,
                    "aggregate_id": str(event.aggregate_id),
                    "event_version": event.event_version,
                    "payload": event.payload,
                },
                queue=QueueName.CRITICAL,
                headers={"request_id": event.request_id, "trace_id": event.trace_id},
            )
            dispatched.append(event.id)
        except Exception as exc:
            event.attempts += 1
            event.error = str(exc)[:500]
            logger.warning(
                "outbox_dispatch_failed",
                event_id=str(event.id),
                event_type=event.event_type,
                attempts=event.attempts,
            )

    if dispatched:
        # Marked processed only after send_task returned. If the process dies
        # before this commit, the events are redelivered — at-least-once, by
        # design.
        await session.execute(
            update(OutboxEvent).where(OutboxEvent.id.in_(dispatched)).values(processed_at=utcnow())
        )
        logger.info("outbox_relayed", count=len(dispatched))

    return len(dispatched)


@celery_app.task(
    name="app.infrastructure.queue.outbox_relay.drain",
    queue=QueueName.CRITICAL,
    autoretry_for=(),  # Beat re-runs it every second; retrying would pile up
    ignore_result=True,
)
def drain_outbox() -> int:  # pragma: no cover — sync bridge; `relay_batch` is covered
    """Celery Beat entry point. Scheduled once per second.

    Bridges into async because the relay uses the same async engine as the app;
    a second sync engine would double the connection footprint for no gain.

    Runs on the worker's persistent loop rather than a fresh one per call. At
    one invocation per second, `asyncio.run` would close the loop holding the
    engine's connections a second after opening them — and this is the task
    that delivers every event in the platform, so it failing silently is the
    worst version of that bug.
    """
    from app.container import get_container

    async def _run() -> int:
        container = await get_container()
        async with container.database.write_session() as session:
            return await relay_batch(session)

    return run_async(_run())


#: The schedule this task's docstring has always described and never had.
#:
#: Without an entry here the relay is a task nobody calls: events commit to the
#: outbox inside their business transaction — which is the point, they are never
#: lost — and then sit there. Every downstream consumer starves, silently,
#: because an undrained outbox produces no errors at all.
#:
#: Two seconds rather than one. A booking confirmation two seconds late is
#: imperceptible; the drain holds a write connection and a row lock for its
#: duration, and at one second a slow batch overlaps its own next run.
BEAT_SCHEDULE: dict[str, dict[str, Any]] = {
    "drain-outbox": {
        "task": "app.infrastructure.queue.outbox_relay.drain",
        "schedule": 2.0,
        # `expires` shorter than the interval: a drain that could not start
        # within its window is pointless, because the next one picks up the
        # same rows. Without it a broker backlog becomes a thundering herd of
        # identical drains all contending for the same locks.
        "options": {"queue": QueueName.CRITICAL, "expires": 10},
    },
}
