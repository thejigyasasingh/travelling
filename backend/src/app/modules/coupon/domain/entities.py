"""Coupons.

Discounts are where a booking platform loses money quietly. Every rule here
exists because its absence is exploitable:

* **The discount applies to accommodation, never to tax.** Tax is collected on
  behalf of the government on the amount actually charged; discounting it means
  remitting money the platform never took.
* **A cap is enforced separately from the percentage.** "20% off" on a ₹4,00,000
  villa week is ₹80,000 — which is why `max_discount_minor` exists and why the
  cap is applied after the percentage, not before.
* **Redemptions are counted, and counted per user.** A code shared on a deals
  forum is used ten thousand times in an hour; a global limit and a per-user
  limit stop different halves of that.
* **The window is checked against the *booking* time, not the stay dates.** A
  coupon valid in September applies to a booking made in September, whatever
  the guest is booking for — otherwise a January promotion silently discounts
  next year's peak season.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Final

from app.core.types.money import Money
from app.modules.coupon.domain import errors
from app.modules.coupon.domain.events import CouponRedeemed
from app.modules.coupon.domain.value_objects import CouponStatus, DiscountType
from app.shared.domain.entity import AggregateRoot

#: Codes are read off posters and typed on mobile keyboards, so the confusable
#: pairs — 0/O and 1/I/L — must not both be available.
#:
#: The **digits** are excluded rather than the letters. Banning O and L would
#: reject MONSOON25 and DIWALI, which is most of what a marketing team wants to
#: write; banning 0 and 1 costs nothing, because a code that cannot contain a
#: zero has no ambiguous O.
_AMBIGUOUS: Final = frozenset("01")
MAX_PERCENT_BPS: Final = 10_000  # 100%


class Coupon(AggregateRoot):
    """A discount code."""

    __slots__ = (
        "applies_to_property_ids",
        "code",
        "description",
        "discount_type",
        "ends_at",
        "first_booking_only",
        "max_discount_minor",
        "min_booking_minor",
        "per_user_limit",
        "redeemed_count",
        "starts_at",
        "status",
        "total_limit",
        "value",
    )

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        code: str,
        description: str,
        discount_type: DiscountType,
        value: int,
        starts_at: datetime,
        ends_at: datetime,
        status: CouponStatus = CouponStatus.ACTIVE,
        min_booking_minor: int = 0,
        max_discount_minor: int | None = None,
        total_limit: int | None = None,
        per_user_limit: int = 1,
        first_booking_only: bool = False,
        applies_to_property_ids: frozenset[uuid.UUID] = frozenset(),
        redeemed_count: int = 0,
        version: int = 1,
    ) -> None:
        super().__init__(entity_id, version)
        self.code = code
        self.description = description
        self.discount_type = discount_type
        self.value = value
        self.starts_at = starts_at
        self.ends_at = ends_at
        self.status = status
        self.min_booking_minor = min_booking_minor
        self.max_discount_minor = max_discount_minor
        self.total_limit = total_limit
        self.per_user_limit = per_user_limit
        self.first_booking_only = first_booking_only
        self.applies_to_property_ids = applies_to_property_ids
        self.redeemed_count = redeemed_count

    @classmethod
    def create(
        cls,
        *,
        code: str,
        description: str,
        discount_type: DiscountType,
        value: int,
        starts_at: datetime,
        ends_at: datetime,
        min_booking_minor: int = 0,
        max_discount_minor: int | None = None,
        total_limit: int | None = None,
        per_user_limit: int = 1,
        first_booking_only: bool = False,
        applies_to_property_ids: frozenset[uuid.UUID] = frozenset(),
    ) -> Coupon:
        normalised = normalise_code(code)

        if ends_at <= starts_at:
            raise errors.InvalidCouponError("ends_at", "must be after the start date")
        if value <= 0:
            raise errors.InvalidCouponError("value", "must be positive")
        if discount_type is DiscountType.PERCENT and value > MAX_PERCENT_BPS:
            raise errors.InvalidCouponError("value", "cannot exceed 100%")
        if per_user_limit < 1:
            raise errors.InvalidCouponError("per_user_limit", "must be at least 1")
        if total_limit is not None and total_limit < 1:
            raise errors.InvalidCouponError("total_limit", "must be at least 1")
        # An uncapped percentage is the single most expensive mistake available
        # here, so it is refused at creation rather than discovered in a report.
        if discount_type is DiscountType.PERCENT and max_discount_minor is None:
            raise errors.InvalidCouponError(
                "max_discount_minor", "is required for a percentage discount"
            )

        return cls(
            code=normalised,
            description=description.strip(),
            discount_type=discount_type,
            value=value,
            starts_at=starts_at,
            ends_at=ends_at,
            min_booking_minor=min_booking_minor,
            max_discount_minor=max_discount_minor,
            total_limit=total_limit,
            per_user_limit=per_user_limit,
            first_booking_only=first_booking_only,
            applies_to_property_ids=applies_to_property_ids,
        )

    # ── validity ──────────────────────────────────────────────────────────

    def assert_redeemable(
        self,
        *,
        now: datetime,
        accommodation_minor: int,
        property_id: uuid.UUID,
        user_redemptions: int,
        is_first_booking: bool,
    ) -> None:
        """Every reason a coupon can be refused, checked in the order a guest
        would find most useful — expiry before eligibility, because "this code
        expired" is actionable and "you are not eligible" is not."""
        if self.status is not CouponStatus.ACTIVE:
            raise errors.CouponNotActiveError(self.code, self.status.value)
        if now < self.starts_at:
            raise errors.CouponNotYetValidError(self.code, self.starts_at)
        if now > self.ends_at:
            raise errors.CouponExpiredError(self.code, self.ends_at)
        if self.total_limit is not None and self.redeemed_count >= self.total_limit:
            raise errors.CouponExhaustedError(self.code)
        if user_redemptions >= self.per_user_limit:
            raise errors.CouponAlreadyUsedError(self.code, self.per_user_limit)
        if self.first_booking_only and not is_first_booking:
            raise errors.CouponFirstBookingOnlyError(self.code)
        if accommodation_minor < self.min_booking_minor:
            raise errors.CouponMinimumNotMetError(self.code, self.min_booking_minor)
        if self.applies_to_property_ids and property_id not in self.applies_to_property_ids:
            raise errors.CouponNotApplicableError(self.code)

    def discount_for(self, accommodation: Money) -> Money:
        """The discount, applied to **accommodation only**.

        Never to tax — that is collected for the government on what was
        actually charged — and never to the cleaning fee, which is a real cost
        the host incurs whatever the guest paid.

        The cap is applied *after* the percentage, and the result can never
        exceed the amount it is discounting: a ₹5,000 flat coupon on a ₹3,000
        booking discounts ₹3,000, not ₹5,000 with ₹2,000 owed back.
        """
        raw = (
            accommodation.amount_minor * self.value // 10_000
            if self.discount_type is DiscountType.PERCENT
            else self.value
        )
        if self.max_discount_minor is not None:
            raw = min(raw, self.max_discount_minor)
        return Money(min(raw, accommodation.amount_minor), accommodation.currency)

    def record_redemption(
        self,
        *,
        booking_id: uuid.UUID,
        user_id: uuid.UUID,
        discount: Money,
        now: datetime,
    ) -> None:
        """Increment the counter and emit the fact.

        The counter here is advisory — the authoritative guard against
        overspending a limited coupon is a unique constraint plus a conditional
        UPDATE in the repository. An in-memory check cannot survive two
        concurrent redemptions of the last remaining code.
        """
        self.redeemed_count += 1
        self.record(
            CouponRedeemed(
                aggregate_id=self.id,
                code=self.code,
                booking_id=booking_id,
                user_id=user_id,
                discount_minor=discount.amount_minor,
                currency=discount.currency,
                redeemed_at=now,
            )
        )

    def deactivate(self) -> None:
        """Stop new redemptions. Bookings already discounted keep their price —
        repricing a confirmed booking is a chargeback."""
        self.status = CouponStatus.INACTIVE

    def activate(self) -> None:
        self.status = CouponStatus.ACTIVE

    @property
    def remaining(self) -> int | None:
        """`None` means unlimited, which is different from zero."""
        if self.total_limit is None:
            return None
        return max(0, self.total_limit - self.redeemed_count)

    def is_live(self, now: datetime) -> bool:
        return (
            self.status is CouponStatus.ACTIVE
            and self.starts_at <= now <= self.ends_at
            and (self.total_limit is None or self.redeemed_count < self.total_limit)
        )

    def as_audit(self) -> dict[str, Any]:
        return {
            "coupon_id": str(self.id),
            "code": self.code,
            "type": self.discount_type.value,
            "value": self.value,
        }


def normalise_code(code: str) -> str:
    """Upper-cased, trimmed, and checked for characters people misread.

    A guest reading `RAINY0FF` off a poster types `RAINYOFF` and gets an error
    they cannot diagnose. Refusing the digit at creation is cheaper than the
    support ticket — and cheaper than refusing the letter, which would rule out
    most words.
    """
    normalised = code.strip().upper().replace(" ", "")
    if not 3 <= len(normalised) <= 24:
        raise errors.InvalidCouponError("code", "must be between 3 and 24 characters")
    if not normalised.isalnum():
        raise errors.InvalidCouponError("code", "must contain only letters and digits")
    ambiguous = _AMBIGUOUS & set(normalised)
    if ambiguous:
        raise errors.InvalidCouponError(
            "code",
            f"cannot contain the digit{'s' if len(ambiguous) > 1 else ''} "
            f"{', '.join(sorted(ambiguous))} — it is misread as "
            f"{'O or L' if ambiguous == {'0', '1'} else ('O' if '0' in ambiguous else 'I or L')}"
            " when read off a poster",
        )
    return normalised
