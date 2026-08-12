"""Half-open stay ranges.

The changeover-day test is the one that matters commercially: if adjacent
bookings are treated as overlapping, every room loses roughly one sellable
night per booking.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.types.date_range import DateRange

pytestmark = pytest.mark.unit


def d(day: int) -> date:
    return date(2026, 9, day)


class TestConstruction:
    def test_night_count_excludes_checkout_day(self) -> None:
        # In on the 5th, out on the 7th = two nights (5th, 6th).
        assert DateRange(d(5), d(7)).night_count == 2

    def test_rejects_same_day(self) -> None:
        with pytest.raises(ValueError, match="strictly after"):
            DateRange(d(5), d(5))

    def test_rejects_reversed(self) -> None:
        with pytest.raises(ValueError, match="strictly after"):
            DateRange(d(7), d(5))

    def test_nights_helper(self) -> None:
        assert DateRange.nights(d(5), 3) == DateRange(d(5), d(8))


class TestOverlap:
    def test_adjacent_ranges_do_not_overlap(self) -> None:
        # Guest A leaves the 7th, guest B arrives the 7th. Both are valid.
        assert not DateRange(d(5), d(7)).overlaps(DateRange(d(7), d(9)))

    def test_partial_overlap(self) -> None:
        assert DateRange(d(5), d(9)).overlaps(DateRange(d(7), d(11)))

    def test_containment(self) -> None:
        assert DateRange(d(1), d(30)).overlaps(DateRange(d(10), d(12)))

    def test_overlap_is_symmetric(self) -> None:
        a, b = DateRange(d(5), d(9)), DateRange(d(7), d(11))
        assert a.overlaps(b) == b.overlaps(a)


class TestOccupancy:
    def test_checkout_day_is_not_occupied(self) -> None:
        stay = DateRange(d(5), d(7))
        assert stay.contains(d(5))
        assert stay.contains(d(6))
        assert not stay.contains(d(7))

    def test_nights_iter_yields_occupied_nights_only(self) -> None:
        assert list(DateRange(d(5), d(8)).nights_iter()) == [d(5), d(6), d(7)]

    def test_pg_literal_matches_the_exclusion_constraint_bounds(self) -> None:
        # Must be '[)' — the same bound the bookings exclusion constraint uses,
        # or the Python check and the database guarantee disagree.
        assert DateRange(d(5), d(7)).to_pg_literal() == "[2026-09-05,2026-09-07)"
