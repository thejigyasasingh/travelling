"""Coupon wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from app.interface.api.deps import ContainerDep
from app.modules.coupon.application.use_cases import (
    CreateCoupon,
    PreviewCoupon,
    SetCouponStatus,
)
from app.modules.coupon.infrastructure.unit_of_work import CouponUow


async def get_coupon_uow(container: ContainerDep) -> AsyncIterator[CouponUow]:
    """The primary, always.

    "Has this code been used up?" answered from a replica is answered from
    data that is a second out of date, and a second is long enough to give away
    the last redemption twice.
    """
    async with container.database.write_session() as session:
        uow = CouponUow(session)
        yield uow
        await uow.flush()


CouponUowDep = Annotated[CouponUow, Depends(get_coupon_uow)]


def create_coupon_uc(container: ContainerDep, uow: CouponUowDep) -> CreateCoupon:
    return CreateCoupon(coupons=uow.coupons, clock=container.clock)


def preview_coupon_uc(container: ContainerDep, uow: CouponUowDep) -> PreviewCoupon:
    return PreviewCoupon(coupons=uow.coupons, clock=container.clock)


def set_coupon_status_uc(container: ContainerDep, uow: CouponUowDep) -> SetCouponStatus:
    return SetCouponStatus(coupons=uow.coupons, clock=container.clock)
