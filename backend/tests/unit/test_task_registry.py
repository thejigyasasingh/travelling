"""Every background job is actually registered, and every name resolves.

This file exists because none of them were.

Task modules live at ``app.modules.<name>.infrastructure.tasks``. Celery was
configured with ``autodiscover_tasks(["app.modules", "app.infrastructure.queue"])``,
which looks for ``app.modules.tasks`` — one layer shallower than reality. No
module was imported, **no task was registered in any process**, and Beat's
schedule was empty.

Nothing about that failed loudly, and that is the part worth defending against.
Beat with an empty schedule sleeps quietly. The outbox relay published to task
names no worker had heard of. ``expire_holds`` never ran, so an abandoned
checkout would have held its rooms forever; ``execute_refund`` never ran, so
every cancellation recorded a refund that was never paid. The system reported
itself healthy throughout.

So the assertions here are deliberately about **wiring, not behaviour**: that a
name someone can queue resolves to code someone can run. Behaviour is tested
elsewhere; this is the check that the plumbing between them is connected.
"""

from __future__ import annotations

import importlib

import pytest

from app.infrastructure.queue.celery_app import (
    TASK_MODULES,
    QueueName,
    celery_app,
    collect_beat_schedule,
)
from app.infrastructure.queue.event_dispatch import SUBSCRIPTIONS

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module", autouse=True)
def _imported() -> None:
    """Import the task modules the way a worker does.

    A worker calls this through `conf.imports`; a test process has not, so
    without it every assertion below would fail for the wrong reason.
    """
    for name in TASK_MODULES:
        importlib.import_module(name)


def registered() -> set[str]:
    return {name for name in celery_app.tasks if name.startswith("app.")}


# ══════════════════════════════════════════════════════════════════════════
# Registration
# ══════════════════════════════════════════════════════════════════════════


def test_tasks_are_registered_at_all() -> None:
    """The regression that started this file. Zero is the failing value."""
    assert registered(), "no Celery task is registered — check conf.imports"


def test_every_declared_task_module_contributes_something() -> None:
    """A module listed in `TASK_MODULES` that registers nothing is either dead
    or misspelled, and both look identical from the outside."""
    for module_name in TASK_MODULES:
        module = importlib.import_module(module_name)
        has_task = any(
            getattr(getattr(module, attr, None), "name", "") in registered()
            for attr in dir(module)
            if not attr.startswith("_")
        )
        assert has_task, f"{module_name} is in TASK_MODULES but registers no task"


def test_the_operationally_critical_jobs_exist() -> None:
    """Named individually rather than counted.

    A count passes when a job is renamed and its scheduler entry is not; these
    four are the ones whose absence is silent and expensive.
    """
    for name in (
        # Releases inventory from lapsed holds. Its absence leaks rooms.
        "app.modules.booking.tasks.expire_holds",
        # Moves money for a cancellation. Its absence is an unpaid refund.
        "app.modules.payment.tasks.execute_refund",
        # Drains the outbox. Its absence stops every event in the system.
        "app.infrastructure.queue.outbox_relay.drain",
        # Sends verification and reset mail. Its absence means no signups.
        "app.modules.notification.tasks.send_notification",
    ):
        assert name in registered(), f"{name} is not registered"


# ══════════════════════════════════════════════════════════════════════════
# Names that must resolve
# ══════════════════════════════════════════════════════════════════════════


def test_every_subscription_points_at_a_real_task() -> None:
    """**The** wiring check.

    `SUBSCRIPTIONS` is a table of strings. A typo, a rename, or a module
    missing from `TASK_MODULES` all produce the same silent outcome: the relay
    queues a message nobody consumes, and the event is lost with no error.
    """
    known = registered()
    for event_type, handlers in SUBSCRIPTIONS.items():
        for task_name in handlers:
            assert task_name in known, f"{event_type} -> {task_name} is not registered"


def test_every_beat_entry_points_at_a_real_task() -> None:
    """Same hazard, other scheduler. Beat logs an unregistered task once per
    tick at a level nobody watches."""
    known = registered()
    for entry_name, entry in collect_beat_schedule().items():
        assert entry["task"] in known, f"beat entry {entry_name} -> {entry['task']} missing"


def test_the_beat_schedule_is_not_empty() -> None:
    assert collect_beat_schedule(), "no scheduled jobs — Beat would run nothing"


def test_beat_entries_have_a_schedule_and_a_queue() -> None:
    """An entry with no queue lands on `default`, where an expiry job that must
    run within the minute queues behind image processing."""
    for entry_name, entry in collect_beat_schedule().items():
        assert entry.get("schedule") is not None, f"{entry_name} has no schedule"
        assert entry.get("options", {}).get("queue"), f"{entry_name} names no queue"


def test_beat_entry_names_are_unique_across_modules() -> None:
    """Beat keys its schedule by name. Two modules using one key silently drops
    a job — `collect_beat_schedule` raises instead, and this is that check."""
    seen: set[str] = set()
    for module_name in TASK_MODULES:
        entries = getattr(importlib.import_module(module_name), "BEAT_SCHEDULE", {}) or {}
        clash = seen & entries.keys()
        assert not clash, f"{module_name} reuses beat entry name(s) {sorted(clash)}"
        seen |= entries.keys()


# ══════════════════════════════════════════════════════════════════════════
# Contracts the dispatcher relies on
# ══════════════════════════════════════════════════════════════════════════


def test_event_consumers_tolerate_unknown_kwargs() -> None:
    """The dispatcher may gain a field; queued messages must survive it.

    `event_type` was added to the dispatch payload for the notification worker.
    A consumer with a closed signature would have raised `TypeError` on every
    message already in flight at deploy time — and for `execute_refund`, those
    messages are refunds.
    """
    import inspect

    known = registered()
    for handlers in SUBSCRIPTIONS.values():
        for task_name in handlers:
            func = celery_app.tasks[task_name].run
            params = inspect.signature(func).parameters.values()
            assert any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params), (
                f"{task_name} does not accept **kwargs and will break when the "
                "dispatcher adds a field"
            )
    assert known  # guards against the loop above vacuously passing


def test_notification_handles_every_event_it_subscribes_to() -> None:
    """The subscription table and the template map have to agree.

    Subscribing to an event the worker cannot turn into a message means the
    mail is dropped after a successful-looking dispatch — the exact failure
    this whole module was built to end.
    """
    from app.modules.notification.infrastructure.tasks import _TEMPLATE_FOR

    subscribed = {
        event_type
        for event_type, handlers in SUBSCRIPTIONS.items()
        if "app.modules.notification.tasks.send_notification" in handlers
    }

    assert subscribed, "the notification worker is subscribed to nothing"
    assert subscribed == set(_TEMPLATE_FOR), (
        f"SUBSCRIPTIONS and _TEMPLATE_FOR disagree: {subscribed ^ set(_TEMPLATE_FOR)}"
    )


def test_every_notification_template_exists() -> None:
    """A mapped template with no renderer is a permanent failure at send time,
    discoverable here in milliseconds instead."""
    from app.modules.notification.domain import templates
    from app.modules.notification.infrastructure.tasks import _TEMPLATE_FOR

    unknown = set(_TEMPLATE_FOR.values()) - templates.known_templates()
    assert not unknown, f"no renderer for {sorted(unknown)}"


def test_notification_runs_on_the_critical_queue() -> None:
    """A verification mail behind a batch of thumbnails is a signup the person
    has already given up on."""
    task = celery_app.tasks["app.modules.notification.tasks.send_notification"]

    assert task.queue == QueueName.CRITICAL
