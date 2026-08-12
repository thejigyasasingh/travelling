"""Availability and the vendor calendar.

**Inventory rows are sparse, and that is the central decision here.**

The obvious design pre-materialises one row per room type per date. At a
million properties with three room types and a two-year booking window, that is
2.2 *billion* rows that mostly say "nothing has happened here" — a table nobody
can vacuum, index or back up, carrying almost no information.

Instead a row exists only when a date **deviates from the default**: something
is booked, blocked, or priced differently. A property with no bookings has zero
inventory rows and is fully available. The read path is therefore:

    units_available(date) = COALESCE(row.units_total, room.total_units)
                          - COALESCE(row.units_booked, 0)
                          and NOT COALESCE(row.is_blocked, false)

which is a ``LEFT JOIN`` with ``COALESCE`` — see ``search_repository.py``. The
cost is that every reader must apply the default; the benefit is a table whose
size tracks actual business activity rather than the calendar.

**This module decides what is *allowed*; it does not enforce it.** The rule
that two guests cannot hold the same unit is a Postgres exclusion constraint
inside the booking transaction, because a check in application code is a
check-then-act race no amount of care can close. What lives here is everything
the *vendor* is allowed to do to their own calendar.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Final

from app.core.types.date_range import DateRange

#: How far ahead a vendor may open inventory. Beyond this the rates are
#: guesses, and a two-year-out booking is far more likely to be cancelled than
#: honoured.
MAX_BOOKING_HORIZON_DAYS: Final = 550


class AvailabilityError(ValueError):
    """A calendar change that would break an existing commitment."""


@dataclass(slots=True)
class DayAvailability:
    """One room type on one date.

    ``units_total`` may differ from the room type's default — a hotel taking
    two of five rooms out for refurbishment sets it to three for those dates
    rather than editing the room type and losing the original number.
    """

    stay_date: date
    units_total: int
    units_booked: int = 0
    is_blocked: bool = False
    rate_override_minor: int | None = None
    min_nights_override: int | None = None
    #: True when no row exists and these values came from the room-type
    #: defaults. Lets the calendar UI show "not customised" and lets a writer
    #: know it must INSERT rather than UPDATE.
    is_default: bool = False

    def __post_init__(self) -> None:
        if self.units_total < 0:
            msg = "units_total cannot be negative"
            raise AvailabilityError(msg)
        if self.units_booked < 0:
            msg = "units_booked cannot be negative"
            raise AvailabilityError(msg)
        if self.units_booked > self.units_total:
            # Should be unreachable — the database has a CHECK constraint for
            # exactly this. Reaching it means a bug or a manual UPDATE, and it
            # is an overbooking, so it fails loudly rather than being clamped.
            msg = (
                f"{self.units_booked} units booked exceeds {self.units_total} total "
                f"on {self.stay_date}"
            )
            raise AvailabilityError(msg)

    @property
    def units_available(self) -> int:
        return 0 if self.is_blocked else max(0, self.units_total - self.units_booked)

    @property
    def is_bookable(self) -> bool:
        return self.units_available > 0

    @property
    def has_commitments(self) -> bool:
        return self.units_booked > 0


@dataclass(slots=True)
class AvailabilityWindow:
    """The resolved calendar for one room type across a date range.

    Built by the repository from sparse rows plus the room-type defaults, so
    every consumer sees a dense view without a dense table.
    """

    room_type_id: object
    span: DateRange
    days: dict[date, DayAvailability] = field(default_factory=dict)

    def day(self, stay_date: date) -> DayAvailability | None:
        return self.days.get(stay_date)

    def __iter__(self) -> Iterator[DayAvailability]:
        for stay_date in self.span.nights_iter():
            if (day := self.days.get(stay_date)) is not None:
                yield day

    @property
    def min_units_available(self) -> int:
        """The binding constraint for the whole stay.

        A guest booking four nights needs the room on *every* one of them, so
        availability for the stay is the minimum across its nights, not the
        average and not the first night.
        """
        values = [d.units_available for d in self]
        return min(values) if values else 0

    def is_available(self, units: int = 1) -> bool:
        return self.min_units_available >= units

    def unavailable_dates(self, units: int = 1) -> list[date]:
        """Which nights block the stay.

        Returned so the UI can say "sold out on the 14th and 15th" and offer
        adjacent dates, instead of a bare "not available" that gives the guest
        nowhere to go.
        """
        return [d.stay_date for d in self if d.units_available < units]

    def next_available_span(self, nights: int, *, units: int = 1) -> DateRange | None:
        """First run of ``nights`` consecutive bookable dates in the window.

        Powers "sold out — but free from the 18th". A guest offered an
        alternative books far more often than one shown a dead end.
        """
        run_start: date | None = None
        run = 0
        for day in self:
            if day.units_available >= units:
                run_start = run_start or day.stay_date
                run += 1
                if run >= nights:
                    assert run_start is not None
                    return DateRange(run_start, run_start + timedelta(days=nights))
            else:
                run_start, run = None, 0
        return None


# ══════════════════════════════════════════════════════════════════════════
# Vendor calendar rules
# ══════════════════════════════════════════════════════════════════════════


def assert_within_horizon(span: DateRange, today: date) -> None:
    """Reject calendar edits outside the sellable window.

    Past dates are rejected because editing them changes nothing a guest can
    buy and only corrupts the historical record that reporting reads.
    """
    if span.start < today:
        msg = "Calendar changes cannot be applied to dates in the past"
        raise AvailabilityError(msg)
    horizon = today + timedelta(days=MAX_BOOKING_HORIZON_DAYS)
    if span.end > horizon:
        msg = f"Calendar changes are limited to {MAX_BOOKING_HORIZON_DAYS} days ahead"
        raise AvailabilityError(msg)


def assert_can_block(window: AvailabilityWindow) -> None:
    """A vendor may close dates — but not dates someone has already booked.

    Allowing it would silently invalidate a confirmed reservation, and the
    guest would only find out at the door. Cancelling an existing booking is a
    separate, deliberate action with a refund and a notification attached.
    """
    committed = [d.stay_date for d in window if d.has_commitments]
    if committed:
        msg = (
            f"{len(committed)} date(s) already have confirmed bookings and cannot be blocked. "
            f"Cancel those bookings first."
        )
        raise AvailabilityError(msg)


def assert_can_reduce_units(window: AvailabilityWindow, new_total: int) -> None:
    """Reducing capacity must not orphan a booking already taken.

    A hotel dropping a room type from five units to two when three are booked
    on the 14th is describing an overbooking. It is refused with the date, so
    the vendor knows exactly which night is the problem.
    """
    if new_total < 0:
        msg = "units_total cannot be negative"
        raise AvailabilityError(msg)
    conflicts = [(d.stay_date, d.units_booked) for d in window if d.units_booked > new_total]
    if conflicts:
        stay_date, booked = conflicts[0]
        msg = (
            f"Cannot reduce to {new_total} units: {booked} are already booked on "
            f"{stay_date.isoformat()}"
            + (f" (and {len(conflicts) - 1} other date(s))" if len(conflicts) > 1 else "")
        )
        raise AvailabilityError(msg)


def build_window(
    *,
    room_type_id: object,
    span: DateRange,
    default_units: int,
    rows: Mapping[date, DayAvailability],
) -> AvailabilityWindow:
    """Densify sparse rows against the room-type default.

    The one place the "missing row means default" convention is applied, so a
    future change to it is a single edit rather than a hunt through every
    reader.
    """
    days = {
        stay_date: rows.get(stay_date)
        or DayAvailability(
            stay_date=stay_date, units_total=default_units, units_booked=0, is_default=True
        )
        for stay_date in span.nights_iter()
    }
    return AvailabilityWindow(room_type_id=room_type_id, span=span, days=days)
