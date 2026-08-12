"""Refund calculation.

Every rupee returned to a guest is decided here, and disputes about it are the
single largest source of support load in a travel marketplace. Four principles
shape the design:

**The policy is data, not code branches.** Each named policy is a table of
(hours before check-in → percentage refunded). Adding a policy, or changing a
threshold for a new market, is an edit to a tuple — not a new ``if`` in a
function that four other things depend on.

**Components refund differently, and that is not a detail.**

* *Accommodation* follows the policy. This is the vendor's compensation for
  holding dates they could have sold to someone else.
* *Cleaning fee* is fully refunded whenever the guest cancels before arrival —
  the vendor has not cleaned anything.
* *Tax* is refunded **in proportion to what is actually refunded**. GST is
  charged on the consideration received; if the guest is only refunded half
  the accommodation, only half the tax on it is reversed. Refunding all the tax
  on a partly-refunded booking means remitting tax we did not collect.
* *Platform fee*, where charged, follows the accommodation.

**Who cancels changes everything.** A vendor cancelling on a guest is not the
same event as a guest changing their mind: the guest is made whole regardless
of policy, because they are about to have their holiday disrupted and must
rebook at whatever the market now charges.

**Rounding never invents or destroys money.** Every split uses
:meth:`Money.allocate`, so components always sum to exactly the refund total.

Nothing here touches a database, a clock it does not own, or a framework — the
whole engine is exercised by ``tests/unit/booking/test_refund_policy.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

from app.core.types.money import Money
from app.modules.booking.domain.value_objects import CancelledBy


class PolicyName(StrEnum):
    FLEXIBLE = "flexible"
    MODERATE = "moderate"
    STRICT = "strict"
    NON_REFUNDABLE = "non_refundable"


@dataclass(frozen=True, slots=True)
class RefundTier:
    """Cancel at least ``hours_before`` ahead and get ``percent`` back."""

    hours_before: int
    percent: Decimal

    def __post_init__(self) -> None:
        if not Decimal("0") <= self.percent <= Decimal("1"):
            msg = "percent must be between 0 and 1"
            raise ValueError(msg)


#: Ladders, most generous threshold first. The first tier whose
#: ``hours_before`` is satisfied wins, so ordering is part of the definition.
POLICY_TIERS: Final[dict[PolicyName, tuple[RefundTier, ...]]] = {
    # Airbnb-style flexible: change your mind up to the day before.
    PolicyName.FLEXIBLE: (
        RefundTier(24, Decimal("1.00")),
        RefundTier(0, Decimal("0.00")),
    ),
    PolicyName.MODERATE: (
        RefundTier(120, Decimal("1.00")),  # 5 days
        RefundTier(24, Decimal("0.50")),
        RefundTier(0, Decimal("0.00")),
    ),
    PolicyName.STRICT: (
        RefundTier(168, Decimal("1.00")),  # 7 days
        RefundTier(72, Decimal("0.50")),
        RefundTier(0, Decimal("0.00")),
    ),
    # Still has a tier table rather than a special case, so the calculation has
    # exactly one shape. Vendors offering this discount the rate in exchange.
    PolicyName.NON_REFUNDABLE: (RefundTier(0, Decimal("0.00")),),
}


@dataclass(frozen=True, slots=True)
class ChargeBreakdown:
    """What the guest actually paid, by component.

    Taken from the booking, not recomputed. Recomputing at cancellation time
    would use *today's* rates and refund an amount that never matches the
    charge — the classic "I paid ₹47,000 and you refunded ₹43,000" ticket.
    """

    accommodation: Money
    extra_guest: Money
    cleaning_fee: Money
    tax: Money
    platform_fee: Money

    @property
    def currency(self) -> str:
        return self.accommodation.currency

    @property
    def total(self) -> Money:
        return (
            self.accommodation + self.extra_guest + self.cleaning_fee + self.tax + self.platform_fee
        )

    @property
    def taxable_base(self) -> Money:
        """What the tax was charged on. Needed to work out the *rate* actually
        applied, which may differ from today's configured rate."""
        return self.accommodation + self.extra_guest


@dataclass(frozen=True, slots=True)
class RefundBreakdown:
    """The decision, itemised.

    Every field exists so the guest can be shown *why*. "You cancelled 40 hours
    before check-in; this property's moderate policy refunds 50% of the room
    rate at that point" resolves a dispute. A bare number starts one.
    """

    policy: PolicyName
    hours_before_check_in: float
    applied_percent: Decimal
    accommodation: Money
    extra_guest: Money
    cleaning_fee: Money
    tax: Money
    platform_fee: Money
    total: Money
    #: Kept by the vendor. Always ``paid - refunded``, by construction.
    vendor_retains: Money
    reason: str
    is_full_refund: bool

    def to_payload(self) -> dict[str, object]:
        return {
            "policy": self.policy.value,
            "hours_before_check_in": round(self.hours_before_check_in, 2),
            "applied_percent": str(self.applied_percent),
            "accommodation_minor": self.accommodation.amount_minor,
            "extra_guest_minor": self.extra_guest.amount_minor,
            "cleaning_fee_minor": self.cleaning_fee.amount_minor,
            "tax_minor": self.tax.amount_minor,
            "platform_fee_minor": self.platform_fee.amount_minor,
            "total_minor": self.total.amount_minor,
            "vendor_retains_minor": self.vendor_retains.amount_minor,
            "reason": self.reason,
            "currency": self.total.currency,
        }


def resolve_tier(policy: PolicyName, hours_before_check_in: float) -> RefundTier:
    """First tier whose threshold is met. Ladders are ordered most-generous
    first, so this is a linear scan of at most three entries."""
    for tier in POLICY_TIERS[policy]:
        if hours_before_check_in >= tier.hours_before:
            return tier
    return RefundTier(0, Decimal("0.00"))


def calculate_refund(
    *,
    charges: ChargeBreakdown,
    policy: PolicyName,
    hours_before_check_in: float,
    cancelled_by: CancelledBy,
    stay_started: bool = False,
) -> RefundBreakdown:
    """Decide what the guest gets back.

    The ordering of the special cases matters and is not arbitrary:

    1. **Vendor or admin cancellation → 100%, policy ignored.** The guest did
       nothing wrong and is about to have their trip disrupted; they will
       rebook at whatever the market now charges, which is usually more. A
       platform that applies the cancellation policy here has vendors dumping
       low-rate bookings whenever demand rises.
    2. **System cancellation (expired hold, failed payment) → 100%.** Nothing
       was ever really charged, and no human decided it.
    3. **Stay already started → 0%.** The room was occupied. A guest leaving
       early negotiates with the vendor; that is not a refund the platform
       computes.
    4. Otherwise the policy ladder applies.
    """
    currency = charges.currency
    zero = Money.zero(currency)

    if cancelled_by in (CancelledBy.VENDOR, CancelledBy.ADMIN):
        return _full_refund(
            charges,
            policy,
            hours_before_check_in,
            reason=f"cancelled_by_{cancelled_by.value}_full_refund",
        )

    if cancelled_by is CancelledBy.SYSTEM:
        return _full_refund(charges, policy, hours_before_check_in, reason="system_cancellation")

    if stay_started:
        return RefundBreakdown(
            policy=policy,
            hours_before_check_in=hours_before_check_in,
            applied_percent=Decimal("0.00"),
            accommodation=zero,
            extra_guest=zero,
            cleaning_fee=zero,
            tax=zero,
            platform_fee=zero,
            total=zero,
            vendor_retains=charges.total,
            reason="stay_already_started",
            is_full_refund=False,
        )

    tier = resolve_tier(policy, hours_before_check_in)
    percent = tier.percent

    accommodation = charges.accommodation.percentage(percent)
    extra_guest = charges.extra_guest.percentage(percent)
    platform_fee = charges.platform_fee.percentage(percent)

    # The vendor has not cleaned anything, so this comes back in full whenever
    # the guest cancels before arrival — even under a strict policy.
    cleaning_fee = charges.cleaning_fee

    tax = _proportional_tax(charges, refunded_taxable=accommodation + extra_guest)

    total = accommodation + extra_guest + cleaning_fee + tax + platform_fee

    return RefundBreakdown(
        policy=policy,
        hours_before_check_in=hours_before_check_in,
        applied_percent=percent,
        accommodation=accommodation,
        extra_guest=extra_guest,
        cleaning_fee=cleaning_fee,
        tax=tax,
        platform_fee=platform_fee,
        total=total,
        vendor_retains=charges.total - total,
        reason=f"{policy.value}_policy_{int(percent * 100)}_percent",
        is_full_refund=total == charges.total,
    )


def _proportional_tax(charges: ChargeBreakdown, *, refunded_taxable: Money) -> Money:
    """Reverse tax in proportion to the taxable amount actually refunded.

    GST is charged on consideration received. Refund half the room rate and
    only half the tax on it is reversed — refunding all of it would mean
    returning tax that was correctly collected and remitted on the half we
    kept, which the platform then eats.

    Derived from the ratio rather than by re-applying today's configured rate:
    the rate may have changed since the booking, and the guest must be refunded
    against what they were actually charged.
    """
    base = charges.taxable_base
    if base.is_zero or charges.tax.is_zero:
        return Money.zero(charges.currency)
    if refunded_taxable.is_zero:
        return Money.zero(charges.currency)

    ratio = Decimal(refunded_taxable.amount_minor) / Decimal(base.amount_minor)
    return charges.tax.percentage(ratio)


def _full_refund(
    charges: ChargeBreakdown,
    policy: PolicyName,
    hours_before: float,
    *,
    reason: str,
) -> RefundBreakdown:
    return RefundBreakdown(
        policy=policy,
        hours_before_check_in=hours_before,
        applied_percent=Decimal("1.00"),
        accommodation=charges.accommodation,
        extra_guest=charges.extra_guest,
        cleaning_fee=charges.cleaning_fee,
        tax=charges.tax,
        platform_fee=charges.platform_fee,
        total=charges.total,
        vendor_retains=Money.zero(charges.currency),
        reason=reason,
        is_full_refund=True,
    )


def describe_policy(policy: PolicyName, currency: str) -> list[dict[str, object]]:
    """Human-readable ladder for the booking screen.

    Shown *before* the guest pays. A cancellation policy discovered only at
    cancellation time is a chargeback, and in several jurisdictions it is not
    enforceable at all.
    """
    return [
        {
            "hours_before_check_in": tier.hours_before,
            "days_before_check_in": round(tier.hours_before / 24, 1),
            "refund_percent": int(tier.percent * 100),
            "currency": currency,
        }
        for tier in POLICY_TIERS[policy]
    ]
