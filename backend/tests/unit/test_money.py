"""Money arithmetic.

These are the tests that stop a rounding bug from becoming a reconciliation
incident. The allocation property in particular is the one that matters: if
splitting a payment across vendor / platform / tax ever loses or invents a
paisa, the daily settlement will not balance and someone will spend a week
finding out why.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.types.money import Money, sum_money

pytestmark = pytest.mark.unit


class TestConstruction:
    def test_from_major_rounds_half_up(self) -> None:
        assert Money.from_major("1499.505", "INR").amount_minor == 149951

    def test_rejects_float(self) -> None:
        # A float has already lost precision before it reaches us; accepting it
        # would make the loss invisible.
        with pytest.raises(TypeError):
            Money.from_major(1499.50, "INR")  # type: ignore[arg-type]

    def test_zero_decimal_currency(self) -> None:
        # JPY has no minor unit. Treating it as 2 would inflate every amount
        # 100x — the classic multi-currency bug.
        assert Money.from_major("1500", "JPY").amount_minor == 1500

    def test_three_decimal_currency(self) -> None:
        assert Money.from_major("10.500", "KWD").amount_minor == 10500

    def test_rejects_unknown_currency(self) -> None:
        with pytest.raises(ValueError, match="Unsupported currency"):
            Money(100, "XYZ")

    def test_rejects_lowercase_currency(self) -> None:
        with pytest.raises(ValueError, match="ISO-4217"):
            Money(100, "inr")


class TestArithmetic:
    def test_add_same_currency(self) -> None:
        assert Money(100, "INR") + Money(250, "INR") == Money(350, "INR")

    def test_refuses_mixed_currency(self) -> None:
        with pytest.raises(ValueError, match="Cannot combine"):
            Money(100, "INR") + Money(100, "USD")

    def test_multiply_by_nights(self) -> None:
        assert Money(250000, "INR") * 3 == Money(750000, "INR")

    def test_refuses_float_multiplication(self) -> None:
        # 0.18 * price is how GST gets silently mis-rounded. percentage()
        # forces the rounding mode to be stated.
        with pytest.raises(TypeError, match="percentage"):
            Money(100, "INR") * 1.18  # type: ignore[operator]

    def test_percentage(self) -> None:
        gst = Money(250000, "INR").percentage(Decimal("0.18"))
        assert gst == Money(45000, "INR")

    def test_sum_of_empty_list_keeps_currency(self) -> None:
        assert sum_money([], "INR") == Money.zero("INR")


class TestAllocation:
    """The invariant: parts always sum to the whole."""

    def test_even_split(self) -> None:
        parts = Money(90000, "INR").allocate([1, 1, 1])
        assert parts == [Money(30000, "INR")] * 3

    def test_indivisible_amount_loses_nothing(self) -> None:
        # 100 paise / 3 does not divide. One part must absorb the remainder.
        parts = Money(100, "INR").allocate([1, 1, 1])
        assert sum(p.amount_minor for p in parts) == 100
        assert sorted(p.amount_minor for p in parts) == [33, 33, 34]

    def test_weighted_split_matches_commission_model(self) -> None:
        # 85% vendor / 12% platform / 3% tax on ₹1,234.57
        parts = Money(123457, "INR").allocate([85, 12, 3])
        assert sum(p.amount_minor for p in parts) == 123457

    @pytest.mark.parametrize("total", [1, 7, 99, 100003, 999999])
    @pytest.mark.parametrize("weights", [[1, 1], [1, 2, 3], [70, 20, 10], [1, 1, 1, 1, 1, 1, 1]])
    def test_allocation_is_lossless(self, total: int, weights: list[int]) -> None:
        parts = Money(total, "INR").allocate(weights)
        assert sum(p.amount_minor for p in parts) == total
        assert len(parts) == len(weights)

    def test_rejects_zero_total_weight(self) -> None:
        with pytest.raises(ValueError, match="positive total"):
            Money(100, "INR").allocate([0, 0])


class TestComparison:
    def test_ordering(self) -> None:
        assert Money(100, "INR") < Money(200, "INR")
        assert Money(200, "INR") >= Money(200, "INR")

    def test_comparison_refuses_mixed_currency(self) -> None:
        with pytest.raises(ValueError, match="Cannot combine"):
            _ = Money(100, "INR") < Money(1, "USD")

    def test_is_immutable(self) -> None:
        price = Money(100, "INR")
        with pytest.raises((AttributeError, TypeError)):
            price.amount_minor = 999  # type: ignore[misc]
