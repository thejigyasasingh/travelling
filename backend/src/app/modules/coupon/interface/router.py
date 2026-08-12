"""Coupon endpoints.

Two audiences on one router, with different permissions: an admin managing
campaigns, and a guest checking whether a code works. The guest-facing preview
is deliberately read-only — it never spends a redemption.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.errors import UnauthenticatedError
from app.core.logging import get_logger
from app.core.types.money import Money
from app.interface.api.deps import ActorDep
from app.modules.auth.domain.rbac import Permission
from app.modules.auth.interface.permissions import RequirePermission
from app.modules.coupon.application.dto import CreateCouponInput
from app.modules.coupon.application.use_cases import (
    CreateCoupon,
    PreviewCoupon,
    SetCouponStatus,
)
from app.modules.coupon.domain.entities import Coupon
from app.modules.coupon.interface import deps
from app.modules.coupon.interface.schemas import (
    CouponListResponse,
    CouponPreviewResponse,
    CouponResponse,
    CouponUsageResponse,
    CreateCouponRequest,
    PreviewCouponRequest,
    SetCouponStatusRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/coupons", tags=["coupons"])
admin_router = APIRouter(prefix="/admin/coupons", tags=["admin: coupons"])

# Campaigns are marketing spend, so they sit behind the same permission as
# refunds rather than behind mere admin access.
CanManage = Depends(RequirePermission(Permission.PAYMENT_REFUND_ANY))


def _to_response(coupon: Coupon) -> CouponResponse:
    return CouponResponse(
        id=coupon.id,
        code=coupon.code,
        description=coupon.description,
        discount_type=coupon.discount_type.value,
        value=coupon.value,
        status=coupon.status.value,
        starts_at=coupon.starts_at,
        ends_at=coupon.ends_at,
        min_booking_minor=coupon.min_booking_minor,
        max_discount_minor=coupon.max_discount_minor,
        total_limit=coupon.total_limit,
        per_user_limit=coupon.per_user_limit,
        first_booking_only=coupon.first_booking_only,
        redeemed_count=coupon.redeemed_count,
        remaining=coupon.remaining,
        property_ids=sorted(coupon.applies_to_property_ids),
    )


@router.post(
    "/preview",
    response_model=CouponPreviewResponse,
    summary="What is this code worth?",
    responses={
        404: {"description": "No such code"},
        409: {"description": "Expired, exhausted, already used, or not applicable"},
    },
)
async def preview(
    body: PreviewCouponRequest,
    actor: ActorDep,
    use_case: Annotated[PreviewCoupon, Depends(deps.preview_coupon_uc)],
) -> CouponPreviewResponse:
    """Check a code without spending it.

    Called while the guest is still deciding, so it deliberately claims
    nothing: a limited campaign must not be exhausted by people who typed a code
    and closed the tab.

    The refusal reasons are distinct on purpose — "expired", "already used" and
    "below the minimum" each have a different thing the guest can do next, and
    collapsing them into "invalid code" is what makes a checkout feel broken.
    """
    if actor.user_id is None:
        # Per-user limits are meaningless without a user, and a preview that
        # ignored them would quote a discount the booking then refuses.
        raise UnauthenticatedError
    accommodation = Money(body.accommodation_minor, body.currency)
    coupon, discount = await use_case.execute(
        code=body.code,
        accommodation=accommodation,
        property_id=body.property_id,
        user_id=actor.user_id,
        # Asked of the booking module in the checkout flow; a preview is
        # advisory and the authoritative check runs again at booking time.
        is_first_booking=True,
    )
    return CouponPreviewResponse(
        code=coupon.code,
        description=coupon.description,
        discount_minor=discount.amount_minor,
        currency=discount.currency,
        accommodation_after_minor=accommodation.amount_minor - discount.amount_minor,
    )


@admin_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CouponResponse,
    dependencies=[CanManage],
    summary="Create a campaign",
    responses={409: {"description": "That code already exists"}},
)
async def create_coupon(
    body: CreateCouponRequest,
    actor: ActorDep,
    use_case: Annotated[CreateCoupon, Depends(deps.create_coupon_uc)],
) -> CouponResponse:
    """A percentage discount **must** carry a cap.

    Refused at creation rather than discovered in a revenue report: 20% off a
    ₹4,00,000 villa week is ₹80,000, and nobody who types "20" is picturing
    that number.
    """
    coupon = await use_case.execute(CreateCouponInput(**body.model_dump()), actor)
    return _to_response(coupon)


@admin_router.get(
    "",
    response_model=CouponListResponse,
    dependencies=[CanManage],
    summary="Campaigns",
)
async def list_coupons(
    uow: deps.CouponUowDep,
    actor: ActorDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=24)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CouponListResponse:
    coupons, total = await uow.coupons.list_for_admin(
        status=status_filter, query=q, limit=size, offset=(page - 1) * size
    )
    return CouponListResponse(
        items=[_to_response(c) for c in coupons], total=total, page=page, size=size
    )


@admin_router.get(
    "/{coupon_id}/usage",
    response_model=CouponUsageResponse,
    dependencies=[CanManage],
    summary="What this campaign cost",
)
async def coupon_usage(
    coupon_id: uuid.UUID,
    uow: deps.CouponUowDep,
    actor: ActorDep,
) -> CouponUsageResponse:
    """Released redemptions are reported separately from live ones — a campaign
    report that silently nets them is one nobody can reconcile."""
    return CouponUsageResponse(**await uow.coupons.usage_summary(coupon_id))


@admin_router.patch(
    "/{coupon_id}/status",
    response_model=CouponResponse,
    dependencies=[CanManage],
    summary="Turn a campaign on or off",
)
async def set_status(
    coupon_id: uuid.UUID,
    body: SetCouponStatusRequest,
    actor: ActorDep,
    use_case: Annotated[SetCouponStatus, Depends(deps.set_coupon_status_uc)],
) -> CouponResponse:
    """Stops new redemptions. Bookings already discounted keep their price —
    repricing a confirmed booking is a chargeback."""
    coupon = await use_case.execute(coupon_id, active=body.active, actor=actor)
    return _to_response(coupon)
