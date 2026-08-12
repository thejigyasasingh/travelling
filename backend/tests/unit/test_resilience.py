"""Retry and the circuit breaker.

The code that decides whether one dependency's bad afternoon becomes an
outage. It sits under every outbound call — the payment gateway, the language
model, object storage — and it is the least exercised code in the codebase
because nothing calls it in a happy path.

Two failure modes it exists to prevent, and both are worse than the failure
they respond to:

* **Retrying a non-idempotent call.** A refund that timed out may well have
  succeeded; retrying it refunds twice. So retry is opt-in per exception type,
  never blanket.
* **Retrying a dependency that is down.** Every retry holds a worker and adds
  load to something already struggling. The breaker is what turns a slow
  cascade into a fast, local failure.
"""

from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.external.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from app.infrastructure.external.resilience.retry import full_jitter, retry_async, with_timeout

pytestmark = pytest.mark.unit
anyio = pytest.mark.asyncio


class Flaky:
    """Fails a set number of times, then succeeds. Counts its calls."""

    def __init__(self, failures: int, exc: type[BaseException] = ConnectionError) -> None:
        self.remaining = failures
        self.calls = 0
        self._exc = exc

    async def __call__(self) -> str:
        self.calls += 1
        if self.remaining > 0:
            self.remaining -= 1
            raise self._exc("upstream is unwell")
        return "ok"


# ══════════════════════════════════════════════════════════════════════════
# Retry
# ══════════════════════════════════════════════════════════════════════════


@anyio
async def test_a_call_that_succeeds_is_not_retried() -> None:
    """The overwhelmingly common case, and it must cost nothing."""
    flaky = Flaky(failures=0)
    assert await retry_async(flaky, attempts=3, base_delay=0.001) == "ok"
    assert flaky.calls == 1


@anyio
async def test_a_transient_failure_is_retried_and_succeeds() -> None:
    flaky = Flaky(failures=2)
    assert await retry_async(flaky, attempts=3, base_delay=0.001) == "ok"
    assert flaky.calls == 3


@anyio
async def test_retries_are_bounded() -> None:
    """An unbounded retry loop is how a dependency outage becomes a thread
    exhaustion outage."""
    flaky = Flaky(failures=99)
    with pytest.raises(ConnectionError):
        await retry_async(flaky, attempts=3, base_delay=0.001)
    assert flaky.calls == 3


@anyio
async def test_an_unlisted_exception_is_not_retried() -> None:
    """**The** retry rule.

    Retry is opt-in per exception type. A `ValueError` means we sent something
    wrong and sending it again will fail the same way; retrying a refund that
    may have already succeeded refunds twice.
    """
    flaky = Flaky(failures=99, exc=ValueError)

    with pytest.raises(ValueError, match="unwell"):
        await retry_async(flaky, attempts=3, base_delay=0.001, retryable=(ConnectionError,))
    assert flaky.calls == 1, "a non-retryable exception was retried"


@anyio
async def test_the_last_exception_is_raised_not_swallowed() -> None:
    """The caller has to be able to see why. A retry helper that raises its own
    generic error throws away the diagnosis."""
    flaky = Flaky(failures=99, exc=TimeoutError)
    with pytest.raises(TimeoutError):
        await retry_async(flaky, attempts=2, base_delay=0.001)


def test_jitter_stays_within_its_bounds() -> None:
    """Full jitter, not exponential-plus-noise.

    Every client retrying at exactly `2^n` seconds reconverges into a
    thundering herd that keeps the dependency down. Spreading uniformly across
    the whole window is what breaks the synchronisation.
    """
    for attempt in range(8):
        for _ in range(50):
            delay = full_jitter(attempt, base=0.5, cap=30.0)
            assert 0.0 <= delay <= 30.0


def test_jitter_is_capped() -> None:
    """Without a cap, the eighth retry of a long outage sleeps for hours."""
    assert full_jitter(attempt=40, base=1.0, cap=10.0) <= 10.0


def test_jitter_actually_varies() -> None:
    """A constant would defeat the point. Asserted because a refactor that
    drops the random term still passes every bounds check above."""
    delays = {full_jitter(3, base=1.0, cap=30.0) for _ in range(100)}
    assert len(delays) > 1


# ══════════════════════════════════════════════════════════════════════════
# Timeout
# ══════════════════════════════════════════════════════════════════════════


@anyio
async def test_a_slow_call_is_cut_off() -> None:
    """A hung upstream holds a worker until something kills it. This is that
    something."""
    with pytest.raises(TimeoutError):
        await with_timeout(asyncio.sleep(5), seconds=0.01, operation="probe")


@anyio
async def test_a_fast_call_returns_its_value() -> None:
    async def quick() -> str:
        return "done"

    assert await with_timeout(quick(), seconds=1.0, operation="probe") == "done"


# ══════════════════════════════════════════════════════════════════════════
# Circuit breaker
# ══════════════════════════════════════════════════════════════════════════


@anyio
async def test_it_starts_closed_and_passes_calls_through() -> None:
    breaker = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))
    assert breaker.state is CircuitState.CLOSED
    assert await breaker.call(Flaky(failures=0)) == "ok"


@anyio
async def test_it_opens_after_the_threshold() -> None:
    """The point of the whole class: stop calling something that is down."""
    breaker = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))
    flaky = Flaky(failures=99)

    for _ in range(2):
        with pytest.raises(ConnectionError):
            await breaker.call(flaky)

    assert breaker.state is CircuitState.OPEN


@anyio
async def test_an_open_circuit_fails_without_calling_upstream() -> None:
    """Fast and local, rather than another timeout on a dependency that is
    already struggling. The saved time is the whole benefit."""
    breaker = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=1))
    flaky = Flaky(failures=99)

    with pytest.raises(ConnectionError):
        await breaker.call(flaky)
    calls_before = flaky.calls

    # A raw string, and deliberately a pattern rather than a literal: the
    # breaker's own exception wording is not the contract here — that it
    # refuses without calling upstream is.
    with pytest.raises(Exception, match=r"(?i)circuit|open|unavailable"):
        await breaker.call(flaky)

    assert flaky.calls == calls_before, "an open circuit still called upstream"


@anyio
async def test_it_recovers_after_the_reset_timeout() -> None:
    """A breaker that never closes is an outage that outlives its cause."""
    breaker = CircuitBreaker(
        "test",
        CircuitBreakerConfig(failure_threshold=1, reset_timeout_seconds=0.05, success_threshold=1),
    )
    flaky = Flaky(failures=1)

    with pytest.raises(ConnectionError):
        await breaker.call(flaky)
    assert breaker.state is CircuitState.OPEN

    await asyncio.sleep(0.06)

    assert await breaker.call(flaky) == "ok"
    assert breaker.state is CircuitState.CLOSED


@anyio
async def test_a_4xx_style_error_does_not_open_the_circuit() -> None:
    """**The** breaker rule.

    A bad request is our fault, not the dependency's. If one malformed payload
    could open the circuit, a single bad booking would block every other
    customer's payment.
    """
    breaker = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))
    flaky = Flaky(failures=99, exc=ValueError)

    for _ in range(5):
        with pytest.raises(ValueError):
            await breaker.call(flaky)

    assert breaker.state is CircuitState.CLOSED, "a client error opened the circuit"


@anyio
async def test_a_success_resets_the_failure_count() -> None:
    """Otherwise failures accumulate across hours of healthy traffic and the
    circuit opens on a dependency that is fine."""
    breaker = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))

    with pytest.raises(ConnectionError):
        await breaker.call(Flaky(failures=1))
    await breaker.call(Flaky(failures=0))

    for _ in range(2):
        with pytest.raises(ConnectionError):
            await breaker.call(Flaky(failures=1))

    assert breaker.state is CircuitState.CLOSED


@anyio
async def test_the_total_budget_stops_retrying_even_with_attempts_left() -> None:
    """Two independent bounds, and the budget is the one that matters.

    `attempts` caps how many times; `total_budget` caps how long. A request
    that has already spent five seconds retrying should give up whether or not
    it has a third attempt available — the caller upstream has a timeout too,
    and exceeding it means the work is wasted anyway.
    """
    flaky = Flaky(failures=99)

    with pytest.raises(ConnectionError):
        await retry_async(flaky, attempts=50, base_delay=0.05, max_delay=0.05, total_budget=0.12)

    assert flaky.calls < 50, "the attempt count overrode the time budget"
