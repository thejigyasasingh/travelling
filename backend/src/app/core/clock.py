"""Time as a dependency.

``datetime.now()`` called directly inside business logic is untestable: you
cannot write "a booking 24h before check-in is refundable" as a test without
either sleeping or monkey-patching a stdlib module. Injecting a clock turns
every time-dependent rule — cancellation windows, token expiry, coupon
validity, payout schedules — into a pure function of its inputs.

The domain layer depends on the :class:`Clock` protocol only. Production wires
:class:`SystemClock`; tests wire :class:`FrozenClock`.

Everything here is timezone-aware UTC. Naive datetimes are banned repo-wide by
ruff's ``DTZ`` rules, because a naive timestamp crossing a process boundary is
a bug that only shows up in October.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime:
        """Current instant, timezone-aware, UTC."""
        ...


class SystemClock:
    """The real clock. The only implementation allowed in production."""

    __slots__ = ()

    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """Deterministic clock for tests.

    Mutable on purpose — ``advance()`` lets a test walk a refund window or a
    token lifetime forward without sleeping.
    """

    __slots__ = ("_now",)

    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 1, 1, tzinfo=UTC)
        if self._now.tzinfo is None:
            msg = "FrozenClock requires a timezone-aware datetime"
            raise ValueError(msg)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> datetime:
        self._now += delta
        return self._now

    def set(self, moment: datetime) -> None:
        self._now = moment


def utcnow() -> datetime:
    """Escape hatch for infrastructure code (logging, metrics, migrations).

    Never call this from ``app.shared.domain`` or a use case — inject a
    :class:`Clock` instead. Kept as one named function so a grep tells you
    exactly where unmockable time is being read.
    """
    return datetime.now(UTC)
