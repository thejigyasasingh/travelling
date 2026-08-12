"""The Celery async bridge.

A regression test for a bug that made **every** background job in the platform
fail after its first run in each worker process.

Tasks are async functions behind synchronous Celery entry points, and every one
of them bridged with ``asyncio.run``. That creates a loop and closes it on
return. The container is a per-process singleton holding a SQLAlchemy engine,
whose pool holds asyncpg connections bound to the loop that opened them — so
task one succeeded and populated the pool, then closed the loop those
connections lived on, and task two failed with ``Event loop is closed``.

A prefork worker runs many tasks per process, so in production this reads as:
refunds stop, holds never expire and the inventory they reserve leaks, payments
are never reconciled, and the outbox stops delivering — all after one task each,
all fixed for exactly one more task by a restart.

The tests below are about the *loop*, not about any one task. If a task module
ever reintroduces ``asyncio.run``, the last test in this file is what catches
it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.infrastructure.queue.async_bridge import run_async

pytestmark = pytest.mark.unit


def test_a_coroutine_runs_and_returns_its_value() -> None:
    async def work() -> int:
        return 42

    assert run_async(work()) == 42


def test_the_loop_survives_between_calls() -> None:
    """**The** regression.

    Two sequential calls is exactly what a worker process does, and it is the
    second one that used to fail.
    """

    async def loop_id() -> int:
        return id(asyncio.get_running_loop())

    first = run_async(loop_id())
    second = run_async(loop_id())

    assert first == second, "each call must not create and close a fresh loop"


def test_many_sequential_calls_all_succeed() -> None:
    """A worker handles hundreds of tasks before it recycles."""

    async def work(n: int) -> int:
        await asyncio.sleep(0)
        return n * 2

    assert [run_async(work(n)) for n in range(50)] == [n * 2 for n in range(50)]


def test_an_object_bound_to_the_loop_stays_usable() -> None:
    """The actual failure shape, without needing a database.

    An `asyncio.Queue` binds to the loop it is first used on, exactly as an
    asyncpg connection does. Reusing one across calls is the thing that broke.
    """
    queue: asyncio.Queue[int] = asyncio.Queue()

    async def put(value: int) -> None:
        await queue.put(value)

    async def drain() -> list[int]:
        return [queue.get_nowait() for _ in range(queue.qsize())]

    run_async(put(1))
    run_async(put(2))
    assert run_async(drain()) == [1, 2]


def test_an_exception_propagates_and_leaves_the_loop_usable() -> None:
    """A failing task must not poison the worker.

    Celery logs the failure and moves on to the next task; if the loop were
    left closed or broken, one bad payload would take out the process for
    everything after it.
    """

    async def boom() -> None:
        msg = "task failed"
        raise ValueError(msg)

    async def fine() -> str:
        return "still here"

    with pytest.raises(ValueError, match="task failed"):
        run_async(boom())
    assert run_async(fine()) == "still here"


def test_a_cancelled_inner_task_does_not_close_the_loop() -> None:
    async def with_cancellation() -> str:
        inner = asyncio.create_task(asyncio.sleep(10))
        inner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await inner
        return "recovered"

    assert run_async(with_cancellation()) == "recovered"
    assert run_async(_identity("after")) == "after"


async def _identity(value: str) -> str:
    return value


def test_no_task_module_uses_asyncio_run() -> None:
    """The rule, enforced rather than documented.

    ``asyncio.run`` in a Celery task is the bug this module exists to prevent,
    and it is a one-line change somebody will make again while adding a task.
    Scanning the source is crude, and it is the only check that survives
    someone not reading this file.

    The CLI is exempt: it is a single-shot process that exits after one
    command, which is precisely where ``asyncio.run`` is correct.
    """
    root = Path(__file__).resolve().parents[2] / "src" / "app"
    offenders = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*.py")
        if path.name == "tasks.py" or "queue" in path.parts
        if "asyncio.run(" in path.read_text() and path.name != "async_bridge.py"
    ]
    assert offenders == [], f"use run_async() in tasks, not asyncio.run: {offenders}"
