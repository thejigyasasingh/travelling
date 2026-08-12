"""Money.

An amount is an **integer count of minor units** (paise, cents) plus an
explicit currency. Never a float, never a bare int.

* Floats cannot represent 0.1. Summing 10,000 line items in float drifts by
  whole currency units, and the payout reconciliation job then fails silently.
* A bare ``int`` loses the currency, so ``total = inr + usd`` typechecks and
  produces a number that means nothing.

Rounding is explicit at every point where it can occur (splits, percentages,
tax) because "who eats the leftover paisa" is a business decision, not a
floating-point accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Self

# Minor-unit exponent. Most currencies are 2; the exceptions bite when a
# JPY amount is silently multiplied by 100.
_MINOR_UNITS: Final[dict[str, int]] = {
    "INR": 2,
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "AED": 2,
    "SGD": 2,
    "AUD": 2,
    "JPY": 0,
    "KWD": 3,
    "BHD": 3,
}


def minor_unit_exponent(currency: str) -> int:
    try:
        return _MINOR_UNITS[currency]
    except KeyError:
        msg = f"Unsupported currency: {currency!r}"
        raise ValueError(msg) from None


@dataclass(frozen=True, slots=True, order=False)
class Money:
    """Immutable amount in a single currency.

    Frozen because a shared mutable price is how a discount applied to one
    booking ends up on another.
    """

    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool):
            msg = "amount_minor must be an int (minor units), not a float or Decimal"
            raise TypeError(msg)
        if len(self.currency) != 3 or not self.currency.isupper():
            msg = f"currency must be an uppercase ISO-4217 code, got {self.currency!r}"
            raise ValueError(msg)
        minor_unit_exponent(self.currency)  # validates support

    # ── constructors ──────────────────────────────────────────────────────

    @classmethod
    def zero(cls, currency: str) -> Self:
        return cls(0, currency)

    @classmethod
    def from_major(cls, amount: Decimal | str | int, currency: str) -> Self:
        """Build from a human-facing amount ("1499.50"). Accepts ``str`` and
        rejects ``float`` — a float argument has already lost precision before
        this function is entered."""
        if isinstance(amount, float):
            msg = "Refusing to build Money from a float; pass a str or Decimal"
            raise TypeError(msg)
        scale = 10 ** minor_unit_exponent(currency)
        minor = (Decimal(amount) * scale).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        return cls(int(minor), currency)

    # ── accessors ─────────────────────────────────────────────────────────

    @property
    def as_major(self) -> Decimal:
        """Presentation only. Never feed this back into arithmetic."""
        return Decimal(self.amount_minor) / Decimal(10) ** minor_unit_exponent(self.currency)

    @property
    def is_zero(self) -> bool:
        return self.amount_minor == 0

    @property
    def is_positive(self) -> bool:
        return self.amount_minor > 0

    # ── arithmetic ────────────────────────────────────────────────────────

    def _check(self, other: Money) -> None:
        if self.currency != other.currency:
            msg = f"Cannot combine {self.currency} with {other.currency}"
            raise ValueError(msg)

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount_minor, self.currency)

    def __mul__(self, factor: int) -> Money:
        """Integer scaling only — 3 nights, 2 rooms.

        Percentage maths goes through :meth:`percentage`, which forces a
        rounding decision instead of hiding one.
        """
        if not isinstance(factor, int) or isinstance(factor, bool):
            msg = "Money can only be multiplied by an int; use percentage() for rates"
            raise TypeError(msg)
        return Money(self.amount_minor * factor, self.currency)

    __rmul__ = __mul__

    def percentage(self, rate: Decimal | str, *, rounding: str = ROUND_HALF_UP) -> Money:
        """Apply a rate (``"0.18"`` for 18% GST) with explicit rounding."""
        value = (Decimal(self.amount_minor) * Decimal(rate)).quantize(Decimal(1), rounding=rounding)
        return Money(int(value), self.currency)

    def allocate(self, weights: list[int]) -> list[Money]:
        """Split without losing or inventing a single minor unit.

        Used for splitting a payout across a vendor, the platform and tax.
        Remainder units are distributed largest-weight-first, so the sum of the
        parts is always exactly the whole — the property that makes
        reconciliation possible.
        """
        if not weights or any(w < 0 for w in weights) or sum(weights) == 0:
            msg = "allocate() requires non-negative weights with a positive total"
            raise ValueError(msg)

        total = sum(weights)
        shares = [self.amount_minor * w // total for w in weights]
        remainder = self.amount_minor - sum(shares)

        for idx in sorted(range(len(weights)), key=lambda i: weights[i], reverse=True):
            if remainder == 0:
                break
            step = 1 if remainder > 0 else -1
            shares[idx] += step
            remainder -= step

        return [Money(s, self.currency) for s in shares]

    # ── comparison ────────────────────────────────────────────────────────

    def __lt__(self, other: Money) -> bool:
        self._check(other)
        return self.amount_minor < other.amount_minor

    def __le__(self, other: Money) -> bool:
        self._check(other)
        return self.amount_minor <= other.amount_minor

    def __gt__(self, other: Money) -> bool:
        self._check(other)
        return self.amount_minor > other.amount_minor

    def __ge__(self, other: Money) -> bool:
        self._check(other)
        return self.amount_minor >= other.amount_minor

    def __str__(self) -> str:
        return f"{self.currency} {self.as_major}"


def sum_money(items: list[Money], currency: str) -> Money:
    """Sum with an explicit currency so an empty list still has one."""
    total = Money.zero(currency)
    for item in items:
        total = total + item
    return total
