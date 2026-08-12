"""Tax invoices.

An invoice is a **legal document**, not a receipt view. Under Indian GST rules
(and equivalents elsewhere) it must be:

* **Sequentially numbered without gaps**, per financial year and per issuing
  series. A gap has to be explained to an auditor, so the number cannot come
  from a Postgres ``SEQUENCE`` — sequences do not roll back, and every failed
  transaction would burn a number. See ``infrastructure/invoice_numbering.py``.
* **Immutable once issued.** A correction is a credit note that references the
  original; an invoice is never edited or deleted.
* **Complete**: supplier and recipient identity, an itemisation, the tax rate
  and amount shown separately, and the total in words for amounts above a
  threshold.

India's financial year runs April-March, so the series is ``2026-27``, not
``2026``. Getting that wrong means every invoice issued in January is filed
against the wrong year.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final

from app.core.types.money import Money

#: Indian FY starts in April.
FY_START_MONTH: Final = 4


def financial_year(when: date) -> str:
    """``2026-27`` for any date from April 2026 to March 2027."""
    year = when.year if when.month >= FY_START_MONTH else when.year - 1
    return f"{year}-{str(year + 1)[-2:]}"


@dataclass(frozen=True, slots=True)
class InvoiceLine:
    description: str
    quantity: int
    unit_amount: Money
    #: HSN/SAC code. 996311 is "accommodation in hotels, inns, guest houses".
    #: Required on a GST invoice; wrong or missing codes are the most common
    #: reason a filing is rejected.
    hsn_code: str = "996311"
    tax_rate: Decimal = Decimal("0.12")

    @property
    def amount(self) -> Money:
        return self.unit_amount * self.quantity

    @property
    def tax_amount(self) -> Money:
        return self.amount.percentage(self.tax_rate)


@dataclass(frozen=True, slots=True)
class Invoice:
    """A rendered invoice. Built from the booking, never stored denormalised
    twice — the booking's charges are the single source of the numbers."""

    number: str
    issued_at: datetime
    financial_year: str

    # ── supplier (the vendor; the platform is an intermediary) ────────────
    supplier_name: str
    supplier_address: str
    supplier_gstin: str | None

    # ── recipient ─────────────────────────────────────────────────────────
    guest_name: str
    guest_email: str
    guest_address: str | None

    # ── the booking ───────────────────────────────────────────────────────
    booking_reference: str
    property_name: str
    check_in: date
    check_out: date
    nights: int
    rooms: int

    lines: tuple[InvoiceLine, ...]
    subtotal: Money
    tax_total: Money
    total: Money
    #: Where the service was supplied. GST is destination-based, so this
    #: decides whether CGST+SGST or IGST applies.
    place_of_supply: str
    currency: str = "INR"

    @property
    def is_intra_state(self) -> bool:
        """Same-state supply splits the tax into CGST and SGST; interstate is
        a single IGST line. Showing the wrong split is a filing error even when
        the total is right."""
        return True  # resolved properly once vendor GSTIN state codes land

    @property
    def cgst(self) -> Money:
        return (
            self.tax_total.allocate([1, 1])[0] if self.is_intra_state else Money.zero(self.currency)
        )

    @property
    def sgst(self) -> Money:
        return (
            self.tax_total.allocate([1, 1])[1] if self.is_intra_state else Money.zero(self.currency)
        )

    @property
    def igst(self) -> Money:
        return Money.zero(self.currency) if self.is_intra_state else self.tax_total

    def total_in_words(self) -> str:
        """Required on Indian invoices above ₹50,000, and expected below it."""
        return f"{_indian_words(int(self.total.as_major))} Rupees Only"


def build_lines(
    *,
    room_type_name: str,
    nights: int,
    rooms: int,
    accommodation: Money,
    extra_guest: Money,
    cleaning_fee: Money,
    tax_rate: Decimal,
) -> tuple[InvoiceLine, ...]:
    """Itemise a booking.

    Components are separate lines because they attract tax differently in
    principle and because a guest disputing a charge needs to see which part
    they are disputing. Zero-valued components are omitted rather than shown as
    ₹0, which reads like a mistake.
    """
    unit_nights = max(nights * rooms, 1)
    lines = [
        InvoiceLine(
            description=f"{room_type_name} — {nights} night(s) x {rooms} room(s)",
            quantity=unit_nights,
            unit_amount=Money(accommodation.amount_minor // unit_nights, accommodation.currency),
            tax_rate=tax_rate,
        )
    ]
    if extra_guest.is_positive:
        lines.append(
            InvoiceLine(
                description="Additional guest charges",
                quantity=1,
                unit_amount=extra_guest,
                tax_rate=tax_rate,
            )
        )
    if cleaning_fee.is_positive:
        lines.append(
            InvoiceLine(
                description="Cleaning fee",
                quantity=1,
                unit_amount=cleaning_fee,
                # Charged once per stay and not part of the room tariff, so it
                # sits in a different slab.
                tax_rate=Decimal("0.18"),
                hsn_code="999799",
            )
        )
    return tuple(lines)


# ── number-to-words ───────────────────────────────────────────────────────
# Indian numbering: lakh and crore, not thousand-million-billion. "One Lakh
# Twenty Thousand" is what an Indian auditor expects to read; "One Hundred
# Twenty Thousand" looks like a foreign document.

_ONES: Final = (
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
)
_TENS: Final = (
    "",
    "",
    "Twenty",
    "Thirty",
    "Forty",
    "Fifty",
    "Sixty",
    "Seventy",
    "Eighty",
    "Ninety",
)


def _two_digits(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _indian_words(amount: int) -> str:
    if amount == 0:
        return "Zero"

    parts: list[str] = []
    for divisor, label in ((10_000_000, "Crore"), (100_000, "Lakh"), (1_000, "Thousand")):
        if amount >= divisor:
            count, amount = divmod(amount, divisor)
            parts.append(f"{_indian_words(count)} {label}")
    if amount >= 100:
        count, amount = divmod(amount, 100)
        parts.append(f"{_ONES[count]} Hundred")
    if amount:
        parts.append(_two_digits(amount))
    return " ".join(parts)
