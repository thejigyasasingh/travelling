"""The pricing engine.

Every number a guest is charged and every number a vendor is paid comes from
here, so these tests are the specification. The rate-resolution order and the
exactness properties are the ones that matter; the rest is arithmetic.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.core.types.date_range import DateRange
from app.core.types.money import Money
from app.modules.property.domain.pricing import (
    PricingError,
    RateCalendar,
    RateConfig,
    cheapest_nightly,
    quote_stay,
    resolve_nightly_rate,
    validate_stay_length,
)

pytestmark = pytest.mark.unit

INR = "INR"


def rate(**kw: object) -> RateConfig:
    defaults: dict[str, object] = {
        "base_rate": Money(500_000, INR),  # ₹5,000
        "included_guests": 2,
        "tax_rate": Decimal("0.12"),
    }
    return RateConfig(**{**defaults, **kw})  # type: ignore[arg-type]


# 2026-06-15 is a Monday, so the 19th/20th are Friday/Saturday.
MON = date(2026, 6, 15)
FRI = date(2026, 6, 19)
SAT = date(2026, 6, 20)
SUN = date(2026, 6, 21)


class TestRateResolution:
    """Most specific source wins: override → weekend → base."""

    def test_base_rate_on_a_weekday(self) -> None:
        night = resolve_nightly_rate(MON, rate())
        assert night.amount == Money(500_000, INR)
        assert night.source == "base"

    def test_weekend_rate_applies_on_friday_and_saturday(self) -> None:
        # Friday and Saturday *nights* are the expensive ones in a leisure
        # market — a guest checking in Friday occupies Friday night.
        config = rate(weekend_rate=Money(800_000, INR))
        assert resolve_nightly_rate(FRI, config).source == "weekend"
        assert resolve_nightly_rate(SAT, config).source == "weekend"
        assert resolve_nightly_rate(SUN, config).source == "base"

    def test_an_override_beats_the_weekend_rate(self) -> None:
        """The single most important line in the resolver.

        If the order were reversed, a vendor's carefully set Diwali rate would
        be silently overwritten by their generic weekend rule — on exactly the
        dates where getting it right matters most.
        """
        config = rate(weekend_rate=Money(800_000, INR))
        night = resolve_nightly_rate(SAT, config, {SAT: Money(2_500_000, INR)})
        assert night.amount == Money(2_500_000, INR)
        assert night.source == "override"

    def test_an_override_in_a_different_currency_is_refused(self) -> None:
        with pytest.raises(PricingError, match="expected INR"):
            resolve_nightly_rate(MON, rate(), {MON: Money(100, "USD")})


class TestQuote:
    def test_prices_night_by_night_not_base_times_nights(self) -> None:
        """A stay spanning a weekend must cost more than base * nights.

        This is the bug a single multiplication produces, and it loses money on
        precisely the dates that generate the most revenue.
        """
        config = rate(weekend_rate=Money(800_000, INR))
        stay = DateRange(date(2026, 6, 18), date(2026, 6, 21))  # Thu, Fri, Sat

        quote = quote_stay(stay, config, billable_guests=2)

        assert [n.source for n in quote.nights] == ["base", "weekend", "weekend"]
        assert quote.accommodation == Money(500_000 + 800_000 + 800_000, INR)

    def test_tax_is_applied_to_the_subtotal_not_per_night(self) -> None:
        # Rounding 12% on each of N nights and summing gives a different — and
        # to a guest with a calculator, wrong-looking — answer.
        stay = DateRange(MON, date(2026, 6, 29))  # 14 nights
        quote = quote_stay(stay, rate(base_rate=Money(333_333, INR)), billable_guests=2)

        expected_tax = (Decimal(333_333 * 14) * Decimal("0.12")).quantize(Decimal(1))
        assert quote.tax.amount_minor == int(expected_tax)

    def test_extra_guests_are_charged_per_night(self) -> None:
        # An extra guest costs the vendor per night, not once per stay.
        config = rate(included_guests=2, extra_guest_rate=Money(100_000, INR))
        stay = DateRange(MON, date(2026, 6, 18))  # 3 nights

        quote = quote_stay(stay, config, billable_guests=4)

        assert quote.extra_guest_total == Money(100_000 * 2 * 3, INR)

    def test_no_extra_charge_within_the_included_count(self) -> None:
        config = rate(included_guests=2, extra_guest_rate=Money(100_000, INR))
        quote = quote_stay(DateRange(MON, SUN), config, billable_guests=2)
        assert quote.extra_guest_total.is_zero

    def test_cleaning_fee_is_once_per_stay_not_per_night(self) -> None:
        # Cleaning a villa costs the same for two nights or ten.
        config = rate(cleaning_fee=Money(300_000, INR))
        short = quote_stay(DateRange(MON, date(2026, 6, 17)), config, billable_guests=2)
        long = quote_stay(DateRange(MON, date(2026, 6, 29)), config, billable_guests=2)
        assert short.cleaning_fee == long.cleaning_fee == Money(300_000, INR)

    def test_cleaning_fee_scales_with_units(self) -> None:
        # Cleaning two villas does cost twice as much.
        config = rate(cleaning_fee=Money(300_000, INR))
        quote = quote_stay(DateRange(MON, SUN), config, billable_guests=2, units=2)
        assert quote.cleaning_fee == Money(600_000, INR)

    def test_total_is_the_sum_of_its_parts(self) -> None:
        # The invariant that makes the breakdown auditable — and makes payout
        # reconciliation possible, since commission is taken on accommodation.
        config = rate(
            weekend_rate=Money(800_000, INR),
            extra_guest_rate=Money(100_000, INR),
            cleaning_fee=Money(250_000, INR),
        )
        quote = quote_stay(
            DateRange(date(2026, 6, 18), date(2026, 6, 22)), config, billable_guests=4
        )
        assert quote.total == (
            quote.accommodation + quote.extra_guest_total + quote.cleaning_fee + quote.tax
        )

    def test_multiple_units_multiply_accommodation(self) -> None:
        quote = quote_stay(DateRange(MON, date(2026, 6, 18)), rate(), billable_guests=2, units=3)
        assert quote.accommodation == Money(500_000 * 3 * 3, INR)

    def test_average_nightly_includes_fees(self) -> None:
        """The headline "per night" number must include what the guest actually
        pays. Excluding a ₹3,000 cleaning fee is the drip-pricing pattern
        regulators are moving against."""
        config = rate(cleaning_fee=Money(300_000, INR))
        quote = quote_stay(DateRange(MON, date(2026, 6, 18)), config, billable_guests=2)
        assert quote.average_nightly.amount_minor > config.base_rate.amount_minor

    def test_breakdown_is_serialisable_and_complete(self) -> None:
        quote = quote_stay(DateRange(MON, date(2026, 6, 18)), rate(), billable_guests=2)
        payload = quote.breakdown()
        assert len(payload["nights"]) == 3
        assert payload["total_minor"] == quote.total.amount_minor

    def test_a_stay_beyond_the_cap_is_refused(self) -> None:
        with pytest.raises(PricingError, match="90 nights"):
            quote_stay(DateRange(MON, date(2026, 12, 31)), rate(), billable_guests=2)


class TestRateConfigValidation:
    def test_rejects_a_non_positive_base_rate(self) -> None:
        with pytest.raises(PricingError, match="base_rate must be positive"):
            RateConfig(base_rate=Money(0, INR))

    def test_rejects_a_mismatched_weekend_currency(self) -> None:
        with pytest.raises(PricingError, match="same currency"):
            RateConfig(base_rate=Money(100, INR), weekend_rate=Money(200, "USD"))

    def test_rejects_max_nights_below_min_nights(self) -> None:
        with pytest.raises(PricingError, match="must not be below"):
            RateConfig(base_rate=Money(100, INR), min_nights=5, max_nights=2)

    def test_rejects_an_implausible_tax_rate(self) -> None:
        with pytest.raises(PricingError, match="tax_rate"):
            RateConfig(base_rate=Money(100, INR), tax_rate=Decimal("0.9"))


class TestStayLength:
    def test_below_the_minimum_is_refused_with_the_number(self) -> None:
        # The UI can then say "this property requires 3 nights" instead of a
        # bare rejection the guest cannot act on.
        with pytest.raises(PricingError, match="minimum stay of 3"):
            validate_stay_length(DateRange(MON, date(2026, 6, 16)), rate(min_nights=3))

    def test_above_the_maximum_is_refused(self) -> None:
        with pytest.raises(PricingError, match="maximum stay of 7"):
            validate_stay_length(DateRange(MON, date(2026, 6, 30)), rate(max_nights=7))

    def test_exactly_the_minimum_is_allowed(self) -> None:
        validate_stay_length(DateRange(MON, date(2026, 6, 18)), rate(min_nights=3))


class TestCheapestNightly:
    def test_never_exceeds_what_the_guest_will_be_quoted(self) -> None:
        """A "from ₹X" that turns out to be higher on the next screen is the
        single most reliable way to lose a booking."""
        config = rate(weekend_rate=Money(800_000, INR))
        overrides = {SAT: Money(2_500_000, INR), MON: Money(300_000, INR)}
        assert cheapest_nightly(config, overrides) == Money(300_000, INR)

    def test_falls_back_to_the_base_rate(self) -> None:
        assert cheapest_nightly(rate()) == Money(500_000, INR)


class TestRateCalendar:
    def test_setting_a_range_writes_every_night(self) -> None:
        calendar = RateCalendar()
        count = calendar.set_range(DateRange(MON, date(2026, 6, 18)), Money(700_000, INR))
        assert count == 3
        assert calendar.get(MON) == Money(700_000, INR)

    def test_clearing_removes_only_what_was_set(self) -> None:
        calendar = RateCalendar()
        calendar.set_range(DateRange(MON, date(2026, 6, 18)), Money(700_000, INR))
        removed = calendar.clear_range(DateRange(MON, date(2026, 6, 20)))
        assert removed == 3
        assert calendar.get(MON) is None
