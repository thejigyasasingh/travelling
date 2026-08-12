"""Coupon rules.

Discounts are where a booking platform loses money quietly, and every rule here
exists because its absence is exploitable. A failure in this file is money
leaving.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.types.money import Money
from app.modules.coupon.domain import errors
from app.modules.coupon.domain.entities import Coupon, normalise_code
from app.modules.coupon.domain.value_objects import CouponStatus, DiscountType

pytestmark = pytest.mark.unit

NOW = datetime.now(UTC).replace(microsecond=0)
INR = "INR"
PROPERTY = uuid.uuid4()


def make(**overrides: object) -> Coupon:
    defaults: dict[str, object] = {
        "code": "MONSOON25",
        "description": "Monsoon sale",
        "discount_type": DiscountType.PERCENT,
        "value": 2500,  # 25%
        "starts_at": NOW - timedelta(days=1),
        "ends_at": NOW + timedelta(days=30),
        "max_discount_minor": 300_000,  # ₹3,000
    }
    return Coupon.create(**(defaults | overrides))  # type: ignore[arg-type]


class TestDiscountArithmetic:
    def test_percentage_is_capped(self) -> None:
        """The most expensive rule in the module.

        25% of a ₹15,000 stay is ₹3,750; the cap holds it at ₹3,000.
        """
        coupon = make()
        assert coupon.discount_for(Money(1_500_000, INR)) == Money(300_000, INR)

    def test_percentage_below_the_cap_is_untouched(self) -> None:
        coupon = make()
        # 25% of ₹4,000 is ₹1,000, well under the ₹3,000 cap.
        assert coupon.discount_for(Money(400_000, INR)) == Money(100_000, INR)

    def test_flat_discount_never_exceeds_the_basket(self) -> None:
        """₹5,000 off a ₹3,000 stay discounts ₹3,000 — not ₹5,000 with ₹2,000
        owed back to the guest."""
        coupon = make(discount_type=DiscountType.FLAT, value=500_000, max_discount_minor=None)
        assert coupon.discount_for(Money(300_000, INR)) == Money(300_000, INR)

    def test_rounding_favours_neither_side_by_accident(self) -> None:
        # 33% of ₹100.01 → integer division, so never a fraction of a paisa.
        coupon = make(value=3300)
        discount = coupon.discount_for(Money(10_001, INR))
        assert discount.amount_minor == 3300
        assert isinstance(discount.amount_minor, int)

    def test_an_uncapped_percentage_is_refused_at_creation(self) -> None:
        """Refused here rather than discovered in a revenue report: 20% of a
        ₹4,00,000 villa week is ₹80,000."""
        with pytest.raises(errors.InvalidCouponError, match="max discount minor is required"):
            make(max_discount_minor=None)

    def test_a_percentage_over_one_hundred_is_refused(self) -> None:
        with pytest.raises(errors.InvalidCouponError):
            make(value=15_000)


class TestRedeemability:
    def kwargs(self, **overrides: object) -> dict[str, object]:
        return {
            "now": NOW,
            "accommodation_minor": 1_500_000,
            "property_id": PROPERTY,
            "user_redemptions": 0,
            "is_first_booking": True,
        } | overrides

    def test_a_live_coupon_passes(self) -> None:
        make().assert_redeemable(**self.kwargs())  # type: ignore[arg-type]

    def test_expired(self) -> None:
        coupon = make(ends_at=NOW + timedelta(days=1))
        with pytest.raises(errors.CouponExpiredError):
            coupon.assert_redeemable(**self.kwargs(now=NOW + timedelta(days=2)))  # type: ignore[arg-type]

    def test_not_yet_started(self) -> None:
        coupon = make(starts_at=NOW + timedelta(days=1))
        with pytest.raises(errors.CouponNotYetValidError):
            coupon.assert_redeemable(**self.kwargs())  # type: ignore[arg-type]

    def test_exhausted(self) -> None:
        coupon = make(total_limit=2)
        coupon.redeemed_count = 2
        with pytest.raises(errors.CouponExhaustedError):
            coupon.assert_redeemable(**self.kwargs())  # type: ignore[arg-type]

    def test_already_used_by_this_guest(self) -> None:
        with pytest.raises(errors.CouponAlreadyUsedError):
            make().assert_redeemable(**self.kwargs(user_redemptions=1))  # type: ignore[arg-type]

    def test_below_the_minimum(self) -> None:
        coupon = make(min_booking_minor=200_000)
        with pytest.raises(errors.CouponMinimumNotMetError):
            coupon.assert_redeemable(**self.kwargs(accommodation_minor=100_000))  # type: ignore[arg-type]

    def test_first_booking_only(self) -> None:
        coupon = make(first_booking_only=True)
        with pytest.raises(errors.CouponFirstBookingOnlyError):
            coupon.assert_redeemable(**self.kwargs(is_first_booking=False))  # type: ignore[arg-type]

    def test_restricted_to_other_properties(self) -> None:
        coupon = make(applies_to_property_ids=frozenset({uuid.uuid4()}))
        with pytest.raises(errors.CouponNotApplicableError):
            coupon.assert_redeemable(**self.kwargs())  # type: ignore[arg-type]

    def test_paused(self) -> None:
        coupon = make()
        coupon.deactivate()
        with pytest.raises(errors.CouponNotActiveError):
            coupon.assert_redeemable(**self.kwargs())  # type: ignore[arg-type]

    def test_each_refusal_is_distinct(self) -> None:
        """Each has a different thing the guest can do next — wait, spend more,
        use another code. Collapsing them into "invalid coupon" is what makes a
        checkout feel broken."""
        codes = {
            errors.CouponExpiredError("X", NOW).code,
            errors.CouponExhaustedError("X").code,
            errors.CouponAlreadyUsedError("X", 1).code,
            errors.CouponMinimumNotMetError("X", 1).code,
            errors.CouponFirstBookingOnlyError("X").code,
            errors.CouponNotApplicableError("X").code,
        }
        assert len(codes) == 6


class TestCodeNormalisation:
    def test_upper_cased_and_trimmed(self) -> None:
        assert normalise_code("  monsoon25 ") == "MONSOON25"

    def test_the_digit_zero_is_refused(self) -> None:
        """`RAINY0FF` on a poster is typed as `RAINYOFF` and fails with an error
        the guest cannot diagnose."""
        with pytest.raises(errors.InvalidCouponError, match="0"):
            normalise_code("RAINY0FF")

    def test_letters_that_look_like_digits_are_allowed(self) -> None:
        """The digits are excluded, not the letters.

        Banning O and L would reject MONSOON and DIWALI, which is most of what
        a marketing team wants to write — and with no 0 in the alphabet, an O
        is unambiguous.
        """
        assert normalise_code("DIWALI") == "DIWALI"
        assert normalise_code("MONSOON") == "MONSOON"

    def test_too_short_or_non_alphanumeric(self) -> None:
        for bad in ("AB", "SUMMER SALE!", "A" * 25):
            with pytest.raises(errors.InvalidCouponError):
                normalise_code(bad)


class TestLifecycle:
    def test_remaining_is_none_for_an_unlimited_coupon(self) -> None:
        """`None` is not zero — rendering it as zero reads as exhausted."""
        assert make().remaining is None
        assert make(total_limit=10).remaining == 10

    def test_redemption_increments_and_records_the_fact(self) -> None:
        coupon = make(total_limit=5)
        coupon.record_redemption(
            booking_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            discount=Money(300_000, INR),
            now=NOW,
        )
        assert coupon.redeemed_count == 1
        assert coupon.remaining == 4
        assert [type(e).__name__ for e in coupon.pull_events()] == ["CouponRedeemed"]

    def test_pausing_stops_new_redemptions(self) -> None:
        coupon = make()
        coupon.deactivate()
        assert coupon.status is CouponStatus.INACTIVE
        assert not coupon.is_live(NOW)
