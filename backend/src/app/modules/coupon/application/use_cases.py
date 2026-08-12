"""Coupon use cases."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.types.money import Money
from app.modules.coupon.application.dto import CreateCouponInput
from app.modules.coupon.application.ports import CouponRepository
from app.modules.coupon.domain import errors
from app.modules.coupon.domain.entities import Coupon
from app.modules.coupon.domain.value_objects import DiscountType
from app.shared.application.use_case import Actor

logger = get_logger(__name__)


@dataclass(slots=True)
class CreateCoupon:
    coupons: CouponRepository
    clock: Clock

    async def execute(self, data: CreateCouponInput, actor: Actor) -> Coupon:
        coupon = Coupon.create(
            code=data.code,
            description=data.description,
            discount_type=DiscountType(data.discount_type),
            value=data.value,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            min_booking_minor=data.min_booking_minor,
            max_discount_minor=data.max_discount_minor,
            total_limit=data.total_limit,
            per_user_limit=data.per_user_limit,
            first_booking_only=data.first_booking_only,
            applies_to_property_ids=frozenset(data.property_ids),
        )
        await self.coupons.add(coupon)
        logger.info("coupon_created", code=coupon.code, by=str(actor.user_id))
        return coupon


@dataclass(slots=True)
class PreviewCoupon:
    """What a code is worth on this basket, without spending it.

    Called from checkout while the guest is still deciding. Deliberately does
    **not** claim a redemption: a guest who types a code and abandons the page
    must not consume one, or a limited campaign is exhausted by window
    shoppers.
    """

    coupons: CouponRepository
    clock: Clock

    async def execute(
        self,
        *,
        code: str,
        accommodation: Money,
        property_id: uuid.UUID,
        user_id: uuid.UUID,
        is_first_booking: bool,
    ) -> tuple[Coupon, Money]:
        coupon = await self.coupons.get_by_code(code)
        if coupon is None:
            raise errors.CouponNotFoundError(code)

        used = await self.coupons.count_user_redemptions(coupon.id, user_id)
        coupon.assert_redeemable(
            now=self.clock.now(),
            accommodation_minor=accommodation.amount_minor,
            property_id=property_id,
            user_redemptions=used,
            is_first_booking=is_first_booking,
        )
        return coupon, coupon.discount_for(accommodation)


@dataclass(slots=True)
class RedeemCoupon:
    """Spend a redemption against a booking.

    Runs inside the booking's transaction, so a coupon is never consumed by a
    booking that fails to commit.
    """

    coupons: CouponRepository
    clock: Clock

    async def execute(
        self,
        *,
        coupon: Coupon,
        booking_id: uuid.UUID,
        user_id: uuid.UUID,
        discount: Money,
    ) -> bool:
        now: datetime = self.clock.now()
        claimed = await self.coupons.claim(
            coupon=coupon,
            booking_id=booking_id,
            user_id=user_id,
            discount=discount,
            now=now,
        )
        if not claimed:
            # Someone took the last one between the preview and here. The
            # booking proceeds at full price rather than failing — losing a
            # discount is an annoyance; losing the booking is a lost sale.
            logger.info("coupon_claim_lost", code=coupon.code, booking_id=str(booking_id))
            return False

        coupon.record_redemption(booking_id=booking_id, user_id=user_id, discount=discount, now=now)
        logger.info(
            "coupon_redeemed",
            code=coupon.code,
            booking_id=str(booking_id),
            discount_minor=discount.amount_minor,
        )
        return True


@dataclass(slots=True)
class ReleaseCoupon:
    """Hand a redemption back when a booking is cancelled."""

    coupons: CouponRepository
    clock: Clock

    async def execute(self, *, coupon_id: uuid.UUID, booking_id: uuid.UUID) -> None:
        await self.coupons.release(coupon_id=coupon_id, booking_id=booking_id, now=self.clock.now())
        logger.info("coupon_released", coupon_id=str(coupon_id), booking_id=str(booking_id))


@dataclass(slots=True)
class SetCouponStatus:
    coupons: CouponRepository
    clock: Clock

    async def execute(self, coupon_id: uuid.UUID, *, active: bool, actor: Actor) -> Coupon:
        coupon = await self.coupons.get(coupon_id)
        if coupon is None:
            raise errors.CouponNotFoundError
        # Bookings already discounted keep their price. Repricing a confirmed
        # booking is a chargeback.
        coupon.activate() if active else coupon.deactivate()
        logger.info(
            "coupon_status_changed",
            code=coupon.code,
            active=active,
            by=str(actor.user_id),
        )
        return coupon
