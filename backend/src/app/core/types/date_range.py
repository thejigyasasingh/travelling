"""Stay ranges.

The single most expensive ambiguity in a booking system is whether the end
date is included. A guest checking in on the 5th and out on the 7th occupies
two nights (5th, 6th) and the room is sellable again on the 7th. Model that
wrong and you either double-book the changeover day or lose a night's revenue
per booking.

:class:`DateRange` is **half-open**: ``[start, end)``. It matches Postgres
``daterange`` with the ``'[)'`` bound, which is what the exclusion constraint
on ``bookings`` uses — so the Python check and the database guarantee agree by
construction rather than by comment.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Self


@dataclass(frozen=True, slots=True)
class DateRange:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end <= self.start:
            msg = f"end ({self.end}) must be strictly after start ({self.start})"
            raise ValueError(msg)

    @classmethod
    def nights(cls, start: date, count: int) -> Self:
        if count < 1:
            msg = "A stay must be at least one night"
            raise ValueError(msg)
        return cls(start, start + timedelta(days=count))

    @property
    def night_count(self) -> int:
        return (self.end - self.start).days

    def overlaps(self, other: DateRange) -> bool:
        """Half-open overlap. Adjacent ranges (one's end == other's start) do
        NOT overlap — that is the changeover day, and it is bookable."""
        return self.start < other.end and other.start < self.end

    def contains(self, day: date) -> bool:
        return self.start <= day < self.end

    def nights_iter(self) -> Iterator[date]:
        """Each occupied night. Yields ``night_count`` dates, excluding the
        checkout date — this is what per-night inventory decrements key on."""
        current = self.start
        while current < self.end:
            yield current
            current += timedelta(days=1)

    def to_pg_literal(self) -> str:
        """Postgres ``daterange`` literal with matching bounds."""
        return f"[{self.start.isoformat()},{self.end.isoformat()})"

    def __str__(self) -> str:
        return f"{self.start.isoformat()}→{self.end.isoformat()} ({self.night_count}n)"
