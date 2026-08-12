"""Nightly pricing.

Every number a guest is shown, and every number a vendor is paid, comes from
here. Three properties are non-negotiable:

**Exactness.** All arithmetic is on :class:`Money` — integer minor units. A
float would drift by paise across a 14-night booking with per-night rates and
percentage tax, and the daily payout reconciliation would fail to balance by a
few rupees that nobody can explain.

**Per-night resolution.** A stay is priced night by night, not
``base * nights``. Rates genuinely vary: weekends, Diwali, a long weekend in
Goa. A single multiplication is the difference between charging correctly and
losing money on exactly the dates that matter most.

**Explainability.** :class:`Quote` carries the per-night breakdown, so
"why ₹47,000?" is answerable from the quote itself. A single total is
unauditable, and it is what turns a pricing question into a support case.

The rate *resolution order* is fixed and is the most important thing in this
file:

    1. a date-specific override (a season, an event, a manual edit)
    2. the weekend rate, if the night falls on one and one is set
    3. the base rate

Most specific wins. If it were the other way round, a vendor's carefully set
Diwali rate would be silently overwritten by their weekend rule.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from app.core.types.date_range import DateRange
from app.core.types.money import Money

#: Saturday and Sunday check-in nights. Friday and Saturday *nights* are the
#: expensive ones in leisure markets — a guest checking in on Friday occupies
#: Friday night — so the weekend is Friday(4) and Saturday(5) by weekday index.
WEEKEND_DAYS: Final = frozenset({4, 5})

MAX_STAY_NIGHTS: Final = 90


class PricingError(ValueError):
    """A rate configuration that cannot produce a valid quote."""


@dataclass(frozen=True, slots=True)
class RateConfig:
    """What a vendor sets for one room type.

    Deliberately small. Every field here is one a vendor can be asked to fill
    in and will understand; anything more expressive (yield curves,
    length-of-stay ladders) belongs in a revenue-management feature, not in the
    field that decides what a guest is charged tonight.
    """

    base_rate: Money
    weekend_rate: Money | None = None
    #: Guests included in the base rate. Beyond this, `extra_guest_rate` is
    #: charged per additional billable guest per night.
    included_guests: int = 2
    extra_guest_rate: Money | None = None
    min_nights: int = 1
    max_nights: int = 30
    #: Applied to the accommodation subtotal. In India this is GST, which is
    #: slab-based on the nightly rate — hence a rate rather than a flat amount.
    tax_rate: Decimal = Decimal("0.12")
    #: A once-per-stay charge, not per night. Cleaning a villa costs the same
    #: whether the guest stays two nights or ten.
    cleaning_fee: Money | None = None

    def __post_init__(self) -> None:
        if not self.base_rate.is_positive:
            msg = "base_rate must be positive"
            raise PricingError(msg)
        if self.weekend_rate is not None and self.weekend_rate.currency != self.base_rate.currency:
            msg = "weekend_rate must use the same currency as base_rate"
            raise PricingError(msg)
        if self.included_guests < 1:
            msg = "included_guests must be at least 1"
            raise PricingError(msg)
        if self.min_nights < 1:
            msg = "min_nights must be at least 1"
            raise PricingError(msg)
        if self.max_nights < self.min_nights:
            msg = "max_nights must not be below min_nights"
            raise PricingError(msg)
        if not Decimal("0") <= self.tax_rate <= Decimal("0.5"):
            msg = "tax_rate must be between 0 and 0.5"
            raise PricingError(msg)

    @property
    def currency(self) -> str:
        return self.base_rate.currency


@dataclass(frozen=True, slots=True)
class NightlyRate:
    """One night, and where its price came from.

    ``source`` exists so the vendor calendar can show *why* a night costs what
    it does — "override" vs "weekend" vs "base" — which is the difference
    between a vendor trusting the calendar and a vendor emailing support.
    """

    stay_date: date
    amount: Money
    source: str  # override | weekend | base

    @property
    def is_weekend(self) -> bool:
        return self.stay_date.weekday() in WEEKEND_DAYS


@dataclass(frozen=True, slots=True)
class Quote:
    """A fully broken-down price for one room type over one date range.

    Every component is separate because they are treated differently
    downstream: tax is remitted, the cleaning fee is usually the vendor's, and
    the accommodation subtotal is what commission is calculated on. A single
    total cannot be split back apart.
    """

    nights: list[NightlyRate]
    accommodation: Money
    extra_guest_total: Money
    cleaning_fee: Money
    tax: Money
    total: Money
    currency: str
    units: int = 1

    @property
    def night_count(self) -> int:
        return len(self.nights)

    @property
    def average_nightly(self) -> Money:
        """What the search results and the price filter compare on.

        Guests compare "per night", but the honest per-night number includes
        the fees they will actually be charged — a headline rate that excludes
        a ₹3,000 cleaning fee is the drip-pricing pattern that regulators are
        increasingly banning.
        """
        if not self.nights:
            return Money.zero(self.currency)
        return Money(self.total.amount_minor // self.night_count, self.currency)

    def breakdown(self) -> dict[str, object]:
        return {
            "nights": [
                {
                    "date": n.stay_date.isoformat(),
                    "amount_minor": n.amount.amount_minor,
                    "source": n.source,
                }
                for n in self.nights
            ],
            "accommodation_minor": self.accommodation.amount_minor,
            "extra_guest_minor": self.extra_guest_total.amount_minor,
            "cleaning_fee_minor": self.cleaning_fee.amount_minor,
            "tax_minor": self.tax.amount_minor,
            "total_minor": self.total.amount_minor,
            "currency": self.currency,
        }


# ══════════════════════════════════════════════════════════════════════════
# Resolution
# ══════════════════════════════════════════════════════════════════════════


def resolve_nightly_rate(
    stay_date: date, config: RateConfig, overrides: Mapping[date, Money] | None = None
) -> NightlyRate:
    """Price one night. Most specific source wins — see the module docstring."""
    if overrides and (override := overrides.get(stay_date)) is not None:
        if override.currency != config.currency:
            msg = f"Override for {stay_date} uses {override.currency}, expected {config.currency}"
            raise PricingError(msg)
        return NightlyRate(stay_date, override, "override")

    if config.weekend_rate is not None and stay_date.weekday() in WEEKEND_DAYS:
        return NightlyRate(stay_date, config.weekend_rate, "weekend")

    return NightlyRate(stay_date, config.base_rate, "base")


def quote_stay(
    stay: DateRange,
    config: RateConfig,
    *,
    billable_guests: int,
    overrides: Mapping[date, Money] | None = None,
    units: int = 1,
) -> Quote:
    """Price a whole stay.

    Order of operations matters and is deliberate:

    1. Sum the per-night accommodation.
    2. Add extra-guest charges **per night**, because an extra guest costs the
       vendor per night, not once.
    3. Add the cleaning fee **once per unit** — cleaning two villas costs twice
       as much as cleaning one, but cleaning one villa for ten nights does not
       cost ten times as much.
    4. Apply tax to the accommodation + extra-guest subtotal.

    Tax is applied to the *subtotal*, not per night. Rounding a 12% tax on each
    of 14 nights and summing gives a different (and, to a guest with a
    calculator, wrong-looking) answer from taxing the total once.
    """
    if stay.night_count > MAX_STAY_NIGHTS:
        msg = f"A stay may not exceed {MAX_STAY_NIGHTS} nights"
        raise PricingError(msg)
    if units < 1:
        msg = "units must be at least 1"
        raise PricingError(msg)

    currency = config.currency
    nights = [resolve_nightly_rate(day, config, overrides) for day in stay.nights_iter()]

    per_unit_accommodation = Money(sum(n.amount.amount_minor for n in nights), currency)
    accommodation = per_unit_accommodation * units

    extra_guest_total = Money.zero(currency)
    extra_guests = max(0, billable_guests - config.included_guests * units)
    if extra_guests and config.extra_guest_rate is not None:
        extra_guest_total = config.extra_guest_rate * (extra_guests * stay.night_count)

    cleaning = (config.cleaning_fee * units) if config.cleaning_fee else Money.zero(currency)

    taxable = accommodation + extra_guest_total
    tax = taxable.percentage(config.tax_rate, rounding=ROUND_HALF_UP)

    return Quote(
        nights=nights,
        accommodation=accommodation,
        extra_guest_total=extra_guest_total,
        cleaning_fee=cleaning,
        tax=tax,
        total=taxable + cleaning + tax,
        currency=currency,
        units=units,
    )


def validate_stay_length(stay: DateRange, config: RateConfig) -> None:
    """Enforce the vendor's minimum and maximum stay.

    Separate from :func:`quote_stay` because a search result should still show
    a price for a 1-night stay at a property with a 3-night minimum — with the
    minimum surfaced — rather than the property vanishing from the results with
    no explanation.
    """
    if stay.night_count < config.min_nights:
        msg = f"This property requires a minimum stay of {config.min_nights} nights"
        raise PricingError(msg)
    if stay.night_count > config.max_nights:
        msg = f"This property allows a maximum stay of {config.max_nights} nights"
        raise PricingError(msg)


def cheapest_nightly(config: RateConfig, overrides: Mapping[date, Money] | None = None) -> Money:
    """The "from ₹X" figure on a search card when no dates are given.

    The lowest rate the property could charge, so the number is never higher
    than what the guest is eventually quoted. A shown price that goes *up* on
    the next screen is the single most reliable way to lose a booking.
    """
    candidates = [config.base_rate]
    if config.weekend_rate is not None:
        candidates.append(config.weekend_rate)
    if overrides:
        candidates.extend(overrides.values())
    return min(candidates, key=lambda m: m.amount_minor)


@dataclass(slots=True)
class RateCalendar:
    """A vendor's per-date overrides for one room type.

    A plain dict of date → Money. Sparse on purpose: a property with a base
    rate and one festival week stores seven rows, not 365. See
    ``availability.py`` for the same reasoning applied to inventory.
    """

    overrides: dict[date, Money] = field(default_factory=dict)

    def set_range(self, span: DateRange, amount: Money) -> int:
        for day in span.nights_iter():
            self.overrides[day] = amount
        return span.night_count

    def clear_range(self, span: DateRange) -> int:
        removed = 0
        for day in span.nights_iter():
            if self.overrides.pop(day, None) is not None:
                removed += 1
        return removed

    def get(self, day: date) -> Money | None:
        return self.overrides.get(day)
