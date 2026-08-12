"""Celery application.

Configuration here is mostly about **not losing work and not doing it twice**.

``acks_late=True`` + ``reject_on_worker_lost=True`` — a task is acknowledged
after it completes, not when it is received. A worker killed mid-task (deploy,
OOM, spot reclaim) returns the task to the queue instead of dropping it. The
cost is that tasks must be idempotent, which they must be anyway: at-least-once
is the only delivery guarantee a broker can actually provide.

``prefetch_multiplier=1`` — the default of 4 lets one worker grab four tasks
and sit on three while running the first. With mixed durations that is
head-of-line blocking: a 5-minute image job holds three 200 ms emails hostage.

**Separate queues with separate worker pools.** ``critical`` (booking
confirmations, payment reconciliation) must never queue behind ``media``
(thumbnailing) or ``bulk`` (a 50k-row vendor import). One queue means the
slowest task defines everyone's latency.

**Redis as broker, with eyes open.** It is not durable like SQS or RabbitMQ.
The transactional outbox is what makes that acceptable: the event is committed
to Postgres in the same transaction as the state change, and the relay
re-publishes anything Redis lost. Redis is the *transport*, never the record.
"""

from __future__ import annotations

from typing import Any, Final

from celery import Celery, Task
from celery.signals import setup_logging, task_failure, task_prerun, worker_ready

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger, request_id_var, trace_id_var

logger = get_logger(__name__)


class QueueName:
    CRITICAL = "critical"  # payments, booking confirmations — SLA: seconds
    DEFAULT = "default"  # notifications, cache warming
    MEDIA = "media"  # image processing — CPU-bound, slow
    BULK = "bulk"  # imports, exports, reports — minutes
    SCHEDULED = "scheduled"  # Beat-driven periodic work


class BaseTask(Task):
    """Default behaviour for every task.

    Autoretry with exponential backoff and jitter is on by default because the
    overwhelming majority of task failures are transient (a dropped connection,
    a rate-limited upstream). Tasks that must *not* retry — anything charging a
    card without an idempotency key — override ``autoretry_for = ()``
    explicitly, so the dangerous case is the one that requires a decision.
    """

    autoretry_for = (ConnectionError, TimeoutError)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 5
    acks_late = True
    reject_on_worker_lost = True

    def on_failure(
        self, exc: Exception, task_id: str, args: Any, kwargs: Any, einfo: Any
    ) -> None:  # pragma: no cover
        logger.error(
            "task_failed",
            task=self.name,
            task_id=task_id,
            error=str(exc),
            error_type=type(exc).__name__,
            exc_info=einfo,
        )


def create_celery_app(settings: Settings | None = None) -> Celery:
    settings = settings or get_settings()
    cfg = settings.celery

    app = Celery("roaming_wandering", task_cls=BaseTask)
    app.conf.update(
        broker_url=settings.redis.broker_url,
        result_backend=settings.redis.broker_url,
        # Results are for a handful of user-visible jobs (export ready?) and
        # nothing else. A day is plenty; longer just fills Redis.
        result_expires=86_400,
        result_extended=True,
        task_ignore_result=True,  # opt in per task
        # ── serialisation ────────────────────────────────────────────────
        # JSON only. Pickle deserialisation is remote code execution for
        # anyone who can write to the broker.
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        # ── reliability ──────────────────────────────────────────────────
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_soft_time_limit=cfg.task_soft_time_limit_seconds,
        task_time_limit=cfg.task_time_limit_seconds,
        broker_connection_retry_on_startup=True,
        broker_transport_options={
            # A task not acked within an hour is redelivered. Must exceed the
            # longest task, or long jobs are silently run twice.
            "visibility_timeout": 3600,
            "max_retries": 3,
        },
        # ── routing ──────────────────────────────────────────────────────
        task_default_queue=QueueName.DEFAULT,
        task_routes={
            "app.modules.payment.*": {"queue": QueueName.CRITICAL},
            "app.modules.booking.tasks.expire_holds": {"queue": QueueName.CRITICAL},
            "app.modules.booking.tasks.*": {"queue": QueueName.SCHEDULED},
            "app.modules.media.*": {"queue": QueueName.MEDIA},
            "app.modules.*.tasks.bulk_*": {"queue": QueueName.BULK},
            "app.infrastructure.queue.outbox_relay.*": {"queue": QueueName.CRITICAL},
        },
        # ── worker hygiene ───────────────────────────────────────────────
        worker_concurrency=cfg.worker_concurrency,
        # Recycle workers periodically: a slow leak in an image library becomes
        # a bounded annoyance instead of an OOM at 3am.
        worker_max_tasks_per_child=1000,
        worker_max_memory_per_child=400_000,  # KiB
        worker_send_task_events=True,
        task_send_sent_event=True,
        timezone="UTC",
        enable_utc=True,
        task_always_eager=cfg.task_always_eager,  # tests run inline
        task_eager_propagates=True,
    )

    # Explicit imports, not autodiscovery.
    #
    # `autodiscover_tasks(["app.modules", ...])` looks for `app.modules.tasks`
    # and `app.infrastructure.queue.tasks`. Neither module exists — the tasks
    # live at `app.modules.<name>.infrastructure.tasks`, one layer deeper than
    # autodiscovery looks. So nothing was ever imported, **no task was ever
    # registered in any process**, and no beat schedule was ever loaded.
    #
    # Nothing failed loudly. Beat had an empty schedule and slept; the relay
    # published events to task names no worker knew; `expire_holds` — which its
    # own docstring calls the most operationally important job here — never ran,
    # so abandoned checkouts would have held inventory indefinitely, and every
    # cancellation would have recorded a refund that was never executed.
    #
    # An explicit list is the fix rather than a corrected glob: it is
    # greppable, it fails loudly on a rename, and `test_task_registry.py`
    # asserts that every task name referenced anywhere resolves to something
    # registered. A convention that silently registers nothing is exactly what
    # got us here.
    app.conf.imports = TASK_MODULES
    return app


#: Every module that defines a Celery task or a beat entry.
#:
#: Add a module here when you add a task. The registry test will fail if you
#: forget, which is the point.
TASK_MODULES: Final[tuple[str, ...]] = (
    "app.infrastructure.queue.event_dispatch",
    "app.infrastructure.queue.outbox_relay",
    "app.modules.ai.infrastructure.tasks",
    "app.modules.booking.infrastructure.tasks",
    "app.modules.notification.infrastructure.tasks",
    "app.modules.payment.infrastructure.tasks",
)


def collect_beat_schedule() -> dict[str, Any]:
    """Merge every module's ``BEAT_SCHEDULE`` into one.

    The schedules are declared next to the tasks they run — which is the right
    place, since the cadence is part of the job's design — and were then never
    collected. Beat read an empty dict and ran nothing.

    Imported lazily inside the function: the task modules import ``celery_app``
    from this module, so importing them at module scope would be circular.
    """
    import importlib

    schedule: dict[str, Any] = {}
    for module_name in TASK_MODULES:
        module = importlib.import_module(module_name)
        entries = getattr(module, "BEAT_SCHEDULE", None)
        if entries:
            overlap = schedule.keys() & entries.keys()
            if overlap:  # pragma: no cover — guarded by the registry test
                msg = f"duplicate beat entries {sorted(overlap)} from {module_name}"
                raise RuntimeError(msg)
            schedule.update(entries)
    return schedule


celery_app = create_celery_app()


@celery_app.on_after_finalize.connect  # pragma: no cover — runs at worker boot
def _load_beat_schedule(sender: Celery, **_: Any) -> None:
    """Attach the collected schedule once the app is finalised.

    On finalize rather than at construction because the task modules import
    this one; importing them any earlier is circular.
    """
    sender.conf.beat_schedule = {**(sender.conf.beat_schedule or {}), **collect_beat_schedule()}


# ── signals ───────────────────────────────────────────────────────────────


@setup_logging.connect
def _configure_worker_logging(**_: Any) -> None:  # pragma: no cover
    """Take over Celery's logging so worker output is structured, scrubbed and
    correlated exactly like the API's."""
    configure_logging(get_settings())


@task_prerun.connect
def _bind_task_context(  # pragma: no cover
    task_id: str | None = None, task: Task | None = None, **kw: Any
) -> None:
    """Propagate correlation IDs from the producer.

    Without this, the log line "booking confirmed" in the API and "email sent"
    in a worker are unlinkable, and debugging a single user's complaint means
    grepping timestamps.
    """
    headers = getattr(task.request, "headers", None) or {} if task else {}
    request_id_var.set(headers.get("request_id"))
    trace_id_var.set(headers.get("trace_id"))
    logger.info("task_started", task=task.name if task else None, task_id=task_id)


@task_failure.connect
def _log_failure(  # pragma: no cover
    task_id: str | None = None, exception: BaseException | None = None, **kw: Any
) -> None:
    logger.error("task_failure_signal", task_id=task_id, error=str(exception))


@worker_ready.connect
def _on_ready(**_: Any) -> None:  # pragma: no cover
    logger.info("celery_worker_ready")
