"""Availability rules and the sparse-inventory convention."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest

from app.core.types.date_range import DateRange
from app.modules.property.domain.availability import (
    MAX_BOOKING_HORIZON_DAYS,
    AvailabilityError,
    DayAvailability,
    assert_can_block,
    assert_can_reduce_units,
    assert_within_horizon,
    build_window,
)

pytestmark = pytest.mark.unit

TODAY = date(2026, 6, 15)
ROOM = uuid.uuid4()


def window(span_days: int = 5, **rows: DayAvailability):
    span = DateRange(TODAY, TODAY + timedelta(days=span_days))
    return build_window(room_type_id=ROOM, span=span, default_units=5, rows=rows)  # type: ignore[arg-type]


def day(offset: int, **kw: object) -> DayAvailability:
    defaults: dict[str, object] = {
        "stay_date": TODAY + timedelta(days=offset),
        "units_total": 5,
        "units_booked": 0,
    }
    return DayAvailability(**{**defaults, **kw})  # type: ignore[arg-type]


class TestSparseDefaults:
    def test_a_date_with_no_row_is_fully_available(self) -> None:
        """The core of the sparse design: absence means default.

        A property with no bookings has zero inventory rows and is fully
        available — which is why the table tracks business activity rather than
        the calendar.
        """
        w = window()
        assert w.min_units_available == 5
        assert all(d.is_default for d in w)

    def test_a_stored_row_overrides_the_default(self) -> None:
        stored = day(2, units_booked=5)
        w = build_window(
            room_type_id=ROOM,
            span=DateRange(TODAY, TODAY + timedelta(days=5)),
            default_units=5,
            rows={stored.stay_date: stored},
        )
        assert w.min_units_available == 0
        assert not w.day(stored.stay_date).is_default  # type: ignore[union-attr]


class TestWindowQueries:
    def test_availability_for_a_stay_is_the_minimum_across_its_nights(self) -> None:
        # A guest needs the room on *every* night, so one sold-out night sinks
        # the whole stay — the average and the first night are both wrong.
        stored = day(2, units_booked=4)
        w = build_window(
            room_type_id=ROOM,
            span=DateRange(TODAY, TODAY + timedelta(days=5)),
            default_units=5,
            rows={stored.stay_date: stored},
        )
        assert w.min_units_available == 1
        assert w.is_available(1)
        assert not w.is_available(2)

    def test_blocked_dates_report_zero_regardless_of_units(self) -> None:
        stored = day(1, units_total=10, units_booked=0, is_blocked=True)
        w = build_window(
            room_type_id=ROOM,
            span=DateRange(TODAY, TODAY + timedelta(days=3)),
            default_units=5,
            rows={stored.stay_date: stored},
        )
        assert w.min_units_available == 0

    def test_unavailable_dates_are_named(self) -> None:
        """So the UI can say "sold out on the 16th and 18th" and offer
        alternatives, instead of a bare "not available" that gives the guest
        nowhere to go."""
        rows = {d.stay_date: d for d in (day(1, units_booked=5), day(3, is_blocked=True))}
        w = build_window(
            room_type_id=ROOM,
            span=DateRange(TODAY, TODAY + timedelta(days=5)),
            default_units=5,
            rows=rows,
        )
        assert w.unavailable_dates() == [TODAY + timedelta(days=1), TODAY + timedelta(days=3)]

    def test_next_available_span_finds_a_run(self) -> None:
        # Powers "sold out — but free from the 18th", which recovers bookings
        # that a dead end would lose.
        blocked = day(1, units_booked=5)
        w = build_window(
            room_type_id=ROOM,
            span=DateRange(TODAY, TODAY + timedelta(days=6)),
            default_units=5,
            rows={blocked.stay_date: blocked},
        )
        span = w.next_available_span(nights=3)
        assert span is not None
        assert span.start == TODAY + timedelta(days=2)

    def test_next_available_span_returns_none_when_there_is_no_run(self) -> None:
        rows = {d.stay_date: d for d in (day(i, units_booked=5) for i in range(5))}
        w = build_window(
            room_type_id=ROOM,
            span=DateRange(TODAY, TODAY + timedelta(days=5)),
            default_units=5,
            rows=rows,
        )
        assert w.next_available_span(nights=2) is None


class TestInvariants:
    def test_booked_beyond_total_is_rejected_loudly(self) -> None:
        """Should be unreachable — the database has a CHECK for it.

        Reaching it means a bug or a manual UPDATE, and it is an overbooking,
        so it fails rather than being silently clamped.
        """
        with pytest.raises(AvailabilityError, match="exceeds"):
            DayAvailability(stay_date=TODAY, units_total=2, units_booked=3)

    def test_negative_counts_are_rejected(self) -> None:
        with pytest.raises(AvailabilityError):
            DayAvailability(stay_date=TODAY, units_total=-1)


class TestVendorGuards:
    def test_blocking_a_booked_date_is_refused(self) -> None:
        """Allowing it would silently invalidate a confirmed reservation, and
        the guest would find out at the door."""
        stored = day(1, units_booked=1)
        w = build_window(
            room_type_id=ROOM,
            span=DateRange(TODAY, TODAY + timedelta(days=3)),
            default_units=5,
            rows={stored.stay_date: stored},
        )
        with pytest.raises(AvailabilityError, match="confirmed bookings"):
            assert_can_block(w)

    def test_blocking_free_dates_is_allowed(self) -> None:
        assert_can_block(window())

    def test_reducing_units_below_what_is_booked_is_refused(self) -> None:
        # A hotel dropping five units to two when three are booked is
        # describing an overbooking.
        stored = day(2, units_booked=3)
        w = build_window(
            room_type_id=ROOM,
            span=DateRange(TODAY, TODAY + timedelta(days=5)),
            default_units=5,
            rows={stored.stay_date: stored},
        )
        with pytest.raises(AvailabilityError, match="3 are already booked"):
            assert_can_reduce_units(w, 2)

    def test_the_error_names_the_offending_date(self) -> None:
        stored = day(2, units_booked=3)
        w = build_window(
            room_type_id=ROOM,
            span=DateRange(TODAY, TODAY + timedelta(days=5)),
            default_units=5,
            rows={stored.stay_date: stored},
        )
        with pytest.raises(AvailabilityError, match=stored.stay_date.isoformat()):
            assert_can_reduce_units(w, 2)

    def test_reducing_to_a_safe_level_is_allowed(self) -> None:
        stored = day(2, units_booked=3)
        w = build_window(
            room_type_id=ROOM,
            span=DateRange(TODAY, TODAY + timedelta(days=5)),
            default_units=5,
            rows={stored.stay_date: stored},
        )
        assert_can_reduce_units(w, 3)

    def test_increasing_capacity_is_always_safe(self) -> None:
        assert_can_reduce_units(window(), 10)


class TestHorizon:
    def test_past_dates_are_refused(self) -> None:
        # Editing them changes nothing anyone can buy and corrupts the history
        # reporting reads.
        with pytest.raises(AvailabilityError, match="past"):
            assert_within_horizon(DateRange(TODAY - timedelta(days=1), TODAY), TODAY)

    def test_beyond_the_horizon_is_refused(self) -> None:
        far = TODAY + timedelta(days=MAX_BOOKING_HORIZON_DAYS + 10)
        with pytest.raises(AvailabilityError, match="days ahead"):
            assert_within_horizon(DateRange(TODAY, far), TODAY)

    def test_today_onwards_within_the_horizon_is_allowed(self) -> None:
        assert_within_horizon(DateRange(TODAY, TODAY + timedelta(days=200)), TODAY)
