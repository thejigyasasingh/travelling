"""Circuit breaker.

A payment gateway that has started timing out is not helped by us continuing
to send it traffic, and neither are we: every in-flight call holds a worker for
the full timeout. At a few hundred RPS that exhausts the pool and a *partner's*
outage becomes *our* outage. This is how one slow dependency takes down an
otherwise healthy API.

Three states, the standard machine:

* **CLOSED** — traffic flows; consecutive failures are counted.
* **OPEN** — fail immediately for ``reset_timeout``. No worker is held. Callers
  get a 503 with ``Retry-After`` in single-digit milliseconds instead of 30s.
* **HALF_OPEN** — after the cooldown, let a small number of probes through. A
  success closes the circuit; a failure re-opens it with the full timeout.
  Limiting probes is what prevents the recovering dependency from being
  slammed by the entire backlog the moment it comes back.

State is per-process, not in Redis. Cross-process state adds a network round
trip to the hot path of every outbound call, and each pod observes the
dependency independently anyway — an instance in a bad AZ *should* open its
own circuit sooner than the others.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypeVar

from app.core.clock import utcnow
from app.core.errors import DependencyUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(slots=True)
class CircuitBreakerConfig:
    failure_threshold: int = 5
    #: Successes needed in HALF_OPEN before closing. >1 avoids flapping on a
    #: single lucky request during a partial recovery.
    success_threshold: int = 2
    reset_timeout_seconds: float = 30.0
    half_open_max_calls: int = 3
    #: Exceptions that count as failures. A 4xx from the gateway means *we*
    #: sent something wrong — it must not open the circuit, or one malformed
    #: request would block every other customer's payment.
    counted_exceptions: tuple[type[BaseException], ...] = (
        TimeoutError,
        ConnectionError,
        asyncio.TimeoutError,
    )


@dataclass(slots=True)
class _CircuitStats:
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    successes: int = 0
    opened_at: float = 0.0
    half_open_calls: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class CircuitBreaker:
    """One instance per dependency — payments, maps, email, SMS.

    Sharing a breaker across dependencies means Google Maps flapping would
    block payments.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._stats = _CircuitStats()

    @property
    def state(self) -> CircuitState:
        return self._stats.state

    async def call(self, fn: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
        await self._before_call()
        try:
            result = await fn(*args, **kwargs)
        except self.config.counted_exceptions as exc:
            await self._on_failure(exc)
            raise
        except Exception:
            # Uncounted (4xx, validation): our fault, not the dependency's.
            # It propagates without moving the circuit.
            raise
        else:
            await self._on_success()
            return result

    async def _before_call(self) -> None:
        stats = self._stats
        async with stats.lock:
            if stats.state is CircuitState.OPEN:
                elapsed = utcnow().timestamp() - stats.opened_at
                if elapsed < self.config.reset_timeout_seconds:
                    raise DependencyUnavailableError(
                        self.name,
                        message=f"{self.name} is unavailable (circuit open)",
                    )
                stats.state = CircuitState.HALF_OPEN
                stats.half_open_calls = 0
                stats.successes = 0
                logger.info("circuit_half_open", circuit=self.name)

            if stats.state is CircuitState.HALF_OPEN:
                if stats.half_open_calls >= self.config.half_open_max_calls:
                    raise DependencyUnavailableError(
                        self.name, message=f"{self.name} is recovering; probes in flight"
                    )
                stats.half_open_calls += 1

    async def _on_success(self) -> None:
        stats = self._stats
        async with stats.lock:
            if stats.state is CircuitState.HALF_OPEN:
                stats.successes += 1
                if stats.successes >= self.config.success_threshold:
                    stats.state = CircuitState.CLOSED
                    stats.failures = 0
                    stats.successes = 0
                    logger.info("circuit_closed", circuit=self.name)
            else:
                stats.failures = 0

    async def _on_failure(self, exc: BaseException) -> None:
        stats = self._stats
        async with stats.lock:
            stats.failures += 1
            if (
                stats.state is CircuitState.HALF_OPEN
                or stats.failures >= self.config.failure_threshold
            ):
                stats.state = CircuitState.OPEN
                stats.opened_at = utcnow().timestamp()
                logger.warning(
                    "circuit_opened",
                    circuit=self.name,
                    failures=stats.failures,
                    error=type(exc).__name__,
                )
