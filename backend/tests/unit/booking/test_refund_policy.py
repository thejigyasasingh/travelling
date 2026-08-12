"""The refund engine.

Every rupee returned to a guest is decided by this code, and disputes about it
are the largest source of support load in a travel marketplace. These tests are
the specification — a failure here is either a policy change someone meant to
make, or money moving wrongly.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.types.money import Money
from app.modules.booking.domain.refund_policy import (
    ChargeBreakdown,
    PolicyName,
    calculate_refund,
    describe_policy,
    resolve_tier,
)
from app.modules.booking.domain.value_objects import CancelledBy

pytestmark = pytest.mark.unit

INR = "INR"


def charges(
    accommodation: int = 1_000_000,  # ₹10,000
    extra_guest: int = 0,
    cleaning: int = 200_000,  # ₹2,000
    tax: int = 120_000,  # 12% of accommodation
    platform: int = 0,
) -> ChargeBreakdown:
    return ChargeBreakdown(
        accommodation=Money(accommodation, INR),
        extra_guest=Money(extra_guest, INR),
        cleaning_fee=Money(cleaning, INR),
        tax=Money(tax, INR),
        platform_fee=Money(platform, INR),
    )


class TestTierResolution:
    def test_flexible_refunds_fully_up_to_24h(self) -> None:
        assert resolve_tier(PolicyName.FLEXIBLE, 25).percent == Decimal("1.00")
        assert resolve_tier(PolicyName.FLEXIBLE, 24).percent == Decimal("1.00")
        assert resolve_tier(PolicyName.FLEXIBLE, 23).percent == Decimal("0.00")

    def test_moderate_has_a_middle_step(self) -> None:
        assert resolve_tier(PolicyName.MODERATE, 121).percent == Decimal("1.00")
        assert resolve_tier(PolicyName.MODERATE, 100).percent == Decimal("0.50")
        assert resolve_tier(PolicyName.MODERATE, 10).percent == Decimal("0.00")

    def test_strict_is_more_demanding_at_every_point(self) -> None:
        # A guest cancelling 6 days out gets everything under moderate and half
        # under strict — that difference is the whole reason both exist.
        assert resolve_tier(PolicyName.MODERATE, 144).percent == Decimal("1.00")
        assert resolve_tier(PolicyName.STRICT, 144).percent == Decimal("0.50")

    def test_non_refundable_returns_nothing_however_early(self) -> None:
        assert resolve_tier(PolicyName.NON_REFUNDABLE, 10_000).percent == Decimal("0.00")

    def test_a_past_check_in_refunds_nothing(self) -> None:
        assert resolve_tier(PolicyName.FLEXIBLE, -5).percent == Decimal("0.00")


class TestComponentTreatment:
    """Components refund differently, and that is not a detail."""

    def test_cleaning_fee_comes_back_even_under_a_strict_policy(self) -> None:
        # The vendor has not cleaned anything.
        result = calculate_refund(
            charges=charges(),
            policy=PolicyName.STRICT,
            hours_before_check_in=1,  # zero accommodation refund
            cancelled_by=CancelledBy.GUEST,
        )
        assert result.accommodation.is_zero
        assert result.cleaning_fee == Money(200_000, INR)

    def test_tax_is_refunded_in_proportion_to_the_accommodation_refunded(self) -> None:
        """The subtle one.

        GST is charged on consideration received. Refund half the room rate and
        only half the tax on it is reversed — refunding all of it means
        returning tax that was correctly collected and remitted on the half we
        kept, which the platform then eats.
        """
        result = calculate_refund(
            charges=charges(accommodation=1_000_000, tax=120_000),
            policy=PolicyName.MODERATE,
            hours_before_check_in=100,  # 50% tier
            cancelled_by=CancelledBy.GUEST,
        )
        assert result.accommodation == Money(500_000, INR)
        assert result.tax == Money(60_000, INR)  # half, not all

    def test_no_tax_is_refunded_when_no_accommodation_is(self) -> None:
        result = calculate_refund(
            charges=charges(),
            policy=PolicyName.STRICT,
            hours_before_check_in=1,
            cancelled_by=CancelledBy.GUEST,
        )
        assert result.tax.is_zero

    def test_extra_guest_charges_follow_the_accommodation(self) -> None:
        result = calculate_refund(
            charges=charges(extra_guest=300_000),
            policy=PolicyName.MODERATE,
            hours_before_check_in=100,
            cancelled_by=CancelledBy.GUEST,
        )
        assert result.extra_guest == Money(150_000, INR)

    def test_the_tax_rate_is_derived_from_what_was_charged(self) -> None:
        # Not from today's configured rate — the vendor may have changed it,
        # and the guest must be refunded against what they actually paid.
        odd = charges(accommodation=1_000_000, tax=180_000)  # 18%, not 12%
        result = calculate_refund(
            charges=odd,
            policy=PolicyName.MODERATE,
            hours_before_check_in=100,
            cancelled_by=CancelledBy.GUEST,
        )
        assert result.tax == Money(90_000, INR)


class TestWhoCancels:
    """Who cancels changes the outcome entirely."""

    def test_a_vendor_cancellation_refunds_in_full_ignoring_the_policy(self) -> None:
        """The guest did nothing wrong and is about to have their trip
        disrupted; they will rebook at today's prices, usually higher.

        A platform that applied the policy here would have vendors dumping
        low-rate bookings whenever demand rose.
        """
        paid = charges()
        result = calculate_refund(
            charges=paid,
            policy=PolicyName.NON_REFUNDABLE,  # the harshest possible
            hours_before_check_in=2,  # the worst possible timing
            cancelled_by=CancelledBy.VENDOR,
        )
        assert result.total == paid.total
        assert result.is_full_refund
        assert result.vendor_retains.is_zero

    def test_an_admin_cancellation_also_refunds_in_full(self) -> None:
        result = calculate_refund(
            charges=charges(),
            policy=PolicyName.STRICT,
            hours_before_check_in=0,
            cancelled_by=CancelledBy.ADMIN,
        )
        assert result.is_full_refund

    def test_a_system_cancellation_refunds_in_full(self) -> None:
        # An expired hold or a failed payment: nothing was really charged, and
        # no human decided it.
        result = calculate_refund(
            charges=charges(),
            policy=PolicyName.NON_REFUNDABLE,
            hours_before_check_in=1,
            cancelled_by=CancelledBy.SYSTEM,
        )
        assert result.is_full_refund

    def test_a_guest_cancellation_follows_the_policy(self) -> None:
        result = calculate_refund(
            charges=charges(),
            policy=PolicyName.NON_REFUNDABLE,
            hours_before_check_in=1_000,
            cancelled_by=CancelledBy.GUEST,
        )
        assert result.accommodation.is_zero


class TestStayStarted:
    def test_nothing_is_refunded_once_the_stay_has_begun(self) -> None:
        # The room was occupied. A guest leaving early negotiates with the
        # vendor; the platform does not compute that.
        result = calculate_refund(
            charges=charges(),
            policy=PolicyName.FLEXIBLE,
            hours_before_check_in=-2,
            cancelled_by=CancelledBy.GUEST,
            stay_started=True,
        )
        assert result.total.is_zero
        assert result.reason == "stay_already_started"

    def test_a_vendor_can_still_refund_a_started_stay_in_full(self) -> None:
        # The vendor check runs before the stay-started check, deliberately: a
        # vendor evicting a guest mid-stay owes them everything.
        result = calculate_refund(
            charges=charges(),
            policy=PolicyName.STRICT,
            hours_before_check_in=-2,
            cancelled_by=CancelledBy.VENDOR,
            stay_started=True,
        )
        assert result.is_full_refund


class TestInvariants:
    @pytest.mark.parametrize("policy", list(PolicyName))
    @pytest.mark.parametrize("hours", [500, 168, 120, 72, 24, 12, 0, -10])
    def test_refund_plus_retained_always_equals_paid(
        self, policy: PolicyName, hours: float
    ) -> None:
        """The invariant that makes reconciliation possible.

        If refund + retained ever drifts from the amount paid, the daily
        settlement fails to balance by an amount nobody can explain.
        """
        paid = charges(accommodation=1_234_567, extra_guest=98_765, cleaning=45_678, tax=159_999)
        result = calculate_refund(
            charges=paid,
            policy=policy,
            hours_before_check_in=hours,
            cancelled_by=CancelledBy.GUEST,
        )
        assert result.total + result.vendor_retains == paid.total

    @pytest.mark.parametrize("policy", list(PolicyName))
    def test_a_refund_never_exceeds_what_was_paid(self, policy: PolicyName) -> None:
        paid = charges()
        for hours in (1_000, 200, 100, 25, 1, -50):
            result = calculate_refund(
                charges=paid,
                policy=policy,
                hours_before_check_in=hours,
                cancelled_by=CancelledBy.GUEST,
            )
            assert result.total.amount_minor <= paid.total.amount_minor

    def test_amounts_with_awkward_arithmetic_still_balance(self) -> None:
        # 1/3 of an odd number of paise, taxed at 12%, is where a float
        # implementation drifts.
        paid = charges(accommodation=333_333, cleaning=1, tax=39_999, extra_guest=7)
        result = calculate_refund(
            charges=paid,
            policy=PolicyName.MODERATE,
            hours_before_check_in=100,
            cancelled_by=CancelledBy.GUEST,
        )
        assert result.total + result.vendor_retains == paid.total


class TestExplainability:
    def test_the_breakdown_says_why(self) -> None:
        # "You cancelled 40 hours before check-in; this property's moderate
        # policy refunds 50% at that point" resolves a dispute. A bare number
        # starts one.
        result = calculate_refund(
            charges=charges(),
            policy=PolicyName.MODERATE,
            hours_before_check_in=40,
            cancelled_by=CancelledBy.GUEST,
        )
        payload = result.to_payload()
        assert payload["policy"] == "moderate"
        assert payload["applied_percent"] == "0.50"
        assert payload["hours_before_check_in"] == 40
        assert "50_percent" in str(payload["reason"])

    def test_the_policy_ladder_is_publishable(self) -> None:
        # Shown before the guest pays. A policy discovered only at cancellation
        # time is a chargeback, and in several jurisdictions unenforceable.
        tiers = describe_policy(PolicyName.MODERATE, INR)
        assert len(tiers) == 3
        assert tiers[0]["refund_percent"] == 100
        assert tiers[0]["days_before_check_in"] == 5.0
