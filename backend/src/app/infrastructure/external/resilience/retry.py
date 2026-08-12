"""Retry policy.

Retrying is not free and is not always safe. Two rules govern every use:

**Only retry idempotent operations.** A ``POST /payments/capture`` that times
out may have succeeded — the response was lost, not the work. Retrying charges
the card twice. Non-idempotent calls get an idempotency key passed to the
upstream instead, and *then* they may be retried.

**Always jitter.** Without it, a thousand clients that failed together retry
together, producing a synchronised thundering herd exactly when the dependency
is trying to recover. Full jitter (``random(0, backoff)``) spreads them out;
it is the variant AWS measured as best in their architecture blog and is the
default here.

Timeout budgets are bounded, not per-attempt: three attempts of 10s each is a
30s worst case, which exceeds any sensible client timeout and holds a worker
for the whole time. ``@resilient`` caps total elapsed time.
"""

from __future__ import annotations

import asyncio
import functools
import random
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from app.core.logging import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")

DEFAULT_RETRYABLE: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    asyncio.TimeoutError,
)


def full_jitter(attempt: int, base: float, cap: float) -> float:
    """``random(0, min(cap, base * 2**attempt))``."""
    return random.uniform(0, min(cap, base * (2**attempt)))  # noqa: S311 — not cryptographic


async def retry_async[T](
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    total_budget: float = 5.0,
    retryable: tuple[type[BaseException], ...] = DEFAULT_RETRYABLE,
    operation: str = "unknown",
) -> T:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + total_budget
    last_exc: BaseException | None = None

    for attempt in range(attempts):
        try:
            return await fn()
        except retryable as exc:
            last_exc = exc
            if attempt == attempts - 1:
                break
            delay = full_jitter(attempt, base_delay, max_delay)
            if loop.time() + delay >= deadline:
                # Sleeping would blow the budget; fail now and let the caller
                # (or the circuit breaker) handle it.
                break
            logger.info(
                "retrying",
                operation=operation,
                attempt=attempt + 1,
                delay_ms=int(delay * 1000),
                error=type(exc).__name__,
            )
            await asyncio.sleep(delay)

    logger.warning("retries_exhausted", operation=operation, attempts=attempts)
    assert last_exc is not None
    raise last_exc


def with_retry(
    *,
    attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    total_budget: float = 5.0,
    retryable: tuple[type[BaseException], ...] = DEFAULT_RETRYABLE,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator form. Apply only to idempotent calls — see the module docstring."""

    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await retry_async(
                lambda: fn(*args, **kwargs),
                attempts=attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                total_budget=total_budget,
                retryable=retryable,
                operation=fn.__qualname__,
            )

        return wrapper

    return decorator


async def with_timeout[T](coro: Awaitable[T], seconds: float, *, operation: str) -> T:
    """Every outbound call gets an explicit timeout.

    httpx's default is *no* timeout. One hung TCP connection then holds an
    event-loop task forever, and enough of them exhaust the pool — the failure
    mode that looks like "the API froze" with no error in any log.
    """
    try:
        async with asyncio.timeout(seconds):
            return await coro
    except TimeoutError:
        logger.warning("operation_timeout", operation=operation, timeout_s=seconds)
        raise


__all__ = ["DEFAULT_RETRYABLE", "full_jitter", "retry_async", "with_retry", "with_timeout"]
