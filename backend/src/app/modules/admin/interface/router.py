"""Admin endpoints.

Every route on this router requires a permission — there is no such thing as a
merely-authenticated admin endpoint. The permissions are the ones already in
the RBAC catalogue, so a support agent sees tickets and bookings but not the
revenue report, and only a superadmin changes roles.

Reads are served from the replica (see `deps.get_read_session`); actions go
through the owning module's use case so its invariants still run.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.logging import get_logger
from app.core.serialization import dto_dict
from app.interface.api.deps import ActorDep
from app.modules.admin.application.dto import PagedResult
from app.modules.admin.application.use_cases import GetAnalytics, GetDashboard
from app.modules.admin.interface import deps
from app.modules.admin.interface.schemas import (
    AdminBookingListResponse,
    AdminBookingResponse,
    AdminPaymentListResponse,
    AdminPaymentResponse,
    AdminPropertyListResponse,
    AdminPropertyResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AdminVendorListResponse,
    AdminVendorResponse,
    AnalyticsResponse,
    CityBreakdownResponse,
    DashboardResponse,
    NotificationListResponse,
    NotificationResponse,
    PageMetaResponse,
    RevenueBreakdownResponse,
)
from app.modules.auth.domain.rbac import Permission
from app.modules.auth.interface.permissions import RequirePermission

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

CanReadUsers = Depends(RequirePermission(Permission.USER_READ_ANY))
CanReadProperties = Depends(RequirePermission(Permission.PROPERTY_READ_INTERNAL))
CanReadBookings = Depends(RequirePermission(Permission.BOOKING_READ_ANY))
CanReadPayments = Depends(RequirePermission(Permission.PAYMENT_READ_ANY))
CanApproveVendors = Depends(RequirePermission(Permission.VENDOR_APPROVE_ANY))


def _meta[T](result: PagedResult[T]) -> PageMetaResponse:
    """Generic because `PagedResult` is invariant: a `PagedResult[UserRow]` is
    not a `PagedResult[object]`, and widening it would need a cast at every
    call site."""
    return PageMetaResponse(
        total=result.total, page=result.page, size=result.size, pages=result.pages
    )


# ══════════════════════════════════════════════════════════════════════════
# Dashboard and analytics
# ══════════════════════════════════════════════════════════════════════════


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    dependencies=[CanReadBookings],
    summary="Everything on the landing screen",
)
async def dashboard(
    actor: ActorDep,
    use_case: Annotated[GetDashboard, Depends(deps.dashboard_uc)],
    window_days: Annotated[int, Query(ge=1, le=90)] = 30,
) -> DashboardResponse:
    """One call, not six.

    The tiles have to agree with each other; six requests issued at slightly
    different moments do not, and an admin who sees "142 bookings" beside
    "₹0 revenue" stops trusting the whole screen.
    """
    view = await use_case.execute(window_days, actor)
    return DashboardResponse(
        kpis=[dto_dict(k) for k in view.kpis],
        bookings_by_day=[dto_dict(p) for p in view.bookings_by_day],
        revenue_by_day=[dto_dict(p) for p in view.revenue_by_day],
        booking_status_mix=view.booking_status_mix,
        top_properties=[dto_dict(p) for p in view.top_properties],
        action_queue=view.action_queue,
        generated_at=view.generated_at,
    )


@router.get(
    "/analytics",
    response_model=AnalyticsResponse,
    dependencies=[CanReadPayments],
    summary="Revenue and demand for a period",
)
async def analytics(
    actor: ActorDep,
    use_case: Annotated[GetAnalytics, Depends(deps.analytics_uc)],
    from_date: date | None = None,
    to_date: date | None = None,
) -> AnalyticsResponse:
    """Gated on payment access rather than booking access: this screen shows
    revenue, fees and vendor payables, which a support agent has no business
    reading."""
    view = await use_case.execute(from_date, to_date, actor)
    return AnalyticsResponse(
        revenue=RevenueBreakdownResponse(
            **dto_dict(view.revenue), net_minor=view.revenue.net_minor
        ),
        bookings_by_day=[dto_dict(p) for p in view.bookings_by_day],
        revenue_by_day=[dto_dict(p) for p in view.revenue_by_day],
        by_city=[
            CityBreakdownResponse(city=city, bookings=count, revenue_minor=revenue)
            for city, count, revenue in view.by_city
        ],
        by_property_type=view.by_property_type,
        cancellation_rate=view.cancellation_rate,
        average_booking_value_minor=view.average_booking_value_minor,
        average_lead_time_days=view.average_lead_time_days,
        occupancy_percent=view.occupancy_percent,
        coupon_cost_minor=view.coupon_cost_minor,
        top_properties=[dto_dict(p) for p in view.top_properties],
    )


# ══════════════════════════════════════════════════════════════════════════
# Lists
# ══════════════════════════════════════════════════════════════════════════


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    dependencies=[CanReadUsers],
    summary="Guests and staff",
)
async def list_users(
    queries: deps.AdminQueriesDep,
    actor: ActorDep,
    q: Annotated[str | None, Query(max_length=120)] = None,
    status: str | None = None,
    role: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminUserListResponse:
    result = await queries.users(query=q, status=status, role=role, page=page, size=size)
    return AdminUserListResponse(
        items=[AdminUserResponse(**dto_dict(row)) for row in result.items],
        meta=_meta(result),
    )


@router.get(
    "/properties",
    response_model=AdminPropertyListResponse,
    dependencies=[CanReadProperties],
    summary="Every listing, any status",
)
async def list_properties(
    queries: deps.AdminQueriesDep,
    actor: ActorDep,
    q: Annotated[str | None, Query(max_length=120)] = None,
    status: str | None = None,
    vendor_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminPropertyListResponse:
    result = await queries.properties(
        query=q, status=status, vendor_id=vendor_id, page=page, size=size
    )
    return AdminPropertyListResponse(
        items=[AdminPropertyResponse(**dto_dict(row)) for row in result.items],
        meta=_meta(result),
    )


@router.get(
    "/bookings",
    response_model=AdminBookingListResponse,
    dependencies=[CanReadBookings],
    summary="Every booking",
)
async def list_bookings(
    queries: deps.AdminQueriesDep,
    actor: ActorDep,
    q: Annotated[str | None, Query(max_length=120)] = None,
    status: str | None = None,
    property_id: uuid.UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminBookingListResponse:
    """`q` matches a booking reference exactly or a guest email loosely —
    the two things support is ever given on a phone call."""
    result = await queries.bookings(
        query=q,
        status=status,
        property_id=property_id,
        from_date=from_date,
        to_date=to_date,
        page=page,
        size=size,
    )
    return AdminBookingListResponse(
        items=[AdminBookingResponse(**dto_dict(row)) for row in result.items],
        meta=_meta(result),
    )


@router.get(
    "/payments",
    response_model=AdminPaymentListResponse,
    dependencies=[CanReadPayments],
    summary="Every payment",
)
async def list_payments(
    queries: deps.AdminQueriesDep,
    actor: ActorDep,
    q: Annotated[str | None, Query(max_length=120)] = None,
    status: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminPaymentListResponse:
    result = await queries.payments(status=status, query=q, page=page, size=size)
    return AdminPaymentListResponse(
        items=[AdminPaymentResponse(**dto_dict(row)) for row in result.items],
        meta=_meta(result),
    )


@router.get(
    "/vendors",
    response_model=AdminVendorListResponse,
    dependencies=[CanApproveVendors],
    summary="Vendor accounts and their applications",
)
async def list_vendors(
    queries: deps.AdminQueriesDep,
    actor: ActorDep,
    q: Annotated[str | None, Query(max_length=120)] = None,
    status: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminVendorListResponse:
    result = await queries.vendors(status=status, query=q, page=page, size=size)
    return AdminVendorListResponse(
        items=[AdminVendorResponse(**dto_dict(row)) for row in result.items],
        meta=_meta(result),
    )


@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    dependencies=[CanReadUsers],
    summary="What the platform has sent",
)
async def list_notifications(
    queries: deps.AdminQueriesDep,
    actor: ActorDep,
    status: str | None = None,
    template: str | None = None,
    recipient: Annotated[str | None, Query(max_length=320)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificationListResponse:
    """Answers "did they get the email?" without anyone opening the provider's
    dashboard — and surfaces failures, which otherwise nobody ever looks at."""
    items, total = await queries.notifications(
        status=status, template=template, recipient=recipient, page=page, size=size
    )
    return NotificationListResponse(
        items=[NotificationResponse(**item) for item in items],
        meta=PageMetaResponse(total=total, page=page, size=size, pages=max(1, -(-total // size))),
    )
