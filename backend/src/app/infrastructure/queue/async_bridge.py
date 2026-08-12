"""Running async code from a synchronous Celery task.

Every task in this codebase is an async function behind a sync Celery entry
point, and the obvious way to bridge that — ``asyncio.run(...)`` — is wrong in a
way that only shows up in production.

``asyncio.run`` creates a fresh event loop and **closes it on return**. The
container is a per-process singleton holding a SQLAlchemy engine, and that
engine's connection pool holds asyncpg connections bound to the loop that
created them. So the first task in a worker process succeeds, populates the
pool, and closes the loop those connections live on; the second task gets a new
loop, checks out a connection from the old one, and fails with
``Event loop is closed`` or ``attached to a different loop``.

A Celery prefork worker runs many tasks per process. The observed behaviour is
therefore: **every worker processes exactly one task successfully and then
fails everything after it** — refunds stop, holds never expire and the
inventory they reserve leaks, payments are never reconciled. Restarting the
workers fixes it for one more task each.

The fix is to give each worker process one long-lived loop and reuse it, which
is also what the pool was sized for. :func:`run_async` is the only supported way
to call an async function from a task; ``asyncio.run`` must not appear in a
task module again.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from celery.signals import worker_process_shutdown

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

#: One per worker process. Created on first use rather than at import, so a
#: module import in a web process does not create a loop nothing will run.
_loop: asyncio.AbstractEventLoop | None = None


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        # Set as *the* loop for this thread too: library code that reaches for
        # `get_event_loop()` — asyncpg's cancellation path among others — must
        # find the same one the connections were opened on.
        asyncio.set_event_loop(_loop)
        logger.debug("worker_loop_created")
    return _loop


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run ``coro`` on this process's persistent event loop.

    Not thread-safe, and does not need to be: Celery's prefork pool runs one
    task at a time per process. If a threaded pool is ever adopted, this needs
    a loop per thread rather than a lock — a lock would serialise every task in
    the worker.
    """
    return _ensure_loop().run_until_complete(coro)


@worker_process_shutdown.connect
def _close_loop(**_: Any) -> None:  # pragma: no cover — process teardown
    """Dispose the engines, then close the loop.

    Order matters. Closing the loop first would leave asyncpg connections
    open with no loop to close them on, and the process exits holding server
    side sessions until Postgres times them out.
    """
    global _loop
    if _loop is None or _loop.is_closed():
        return
    try:
        from app.container import reset_container

        _loop.run_until_complete(reset_container())
    except Exception as exc:
        logger.warning("worker_shutdown_incomplete", error=str(exc)[:200])
    finally:
        _loop.close()
        _loop = None
        logger.debug("worker_loop_closed")
