"""Vendor endpoints: applying, and being reviewed."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import PlainTextResponse

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.core.serialization import dto_dict
from app.interface.api.deps import ActorDep
from app.modules.admin.interface.schemas import (
    ApproveVendorRequest,
    RejectVendorRequest,
    SuspendVendorRequest,
)
from app.modules.auth.domain.rbac import Permission
from app.modules.auth.interface.permissions import RequirePermission
from app.modules.vendor.application.use_cases.manage import RegisterVendor, ReviewVendor
from app.modules.vendor.domain.entities import Vendor
from app.modules.vendor.domain.errors import VendorNotFoundError
from app.modules.vendor.interface import deps
from app.modules.vendor.interface.schemas import (
    ArrivalResponse,
    EarningsResponse,
    MonthlyStatementRow,
    OccupancyResponse,
    PropertyPerformanceResponse,
    RegisterVendorRequest,
    ReportsResponse,
    RevenuePointResponse,
    UpdateBankRequest,
    VendorDashboardResponse,
    VendorResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/vendor", tags=["vendor"])
admin_router = APIRouter(prefix="/admin/vendors", tags=["admin: vendors"])

CanApprove = Depends(RequirePermission(Permission.VENDOR_APPROVE_ANY))


def _to_response(vendor: Vendor) -> VendorResponse:
    return VendorResponse(
        id=vendor.id,
        legal_name=vendor.legal_name,
        display_name=vendor.display_name,
        contact_email=vendor.contact_email,
        contact_phone=vendor.contact_phone,
        status=vendor.status.value,
        gstin=vendor.gstin,
        pan=vendor.pan,
        bank_account_last4=vendor.bank_account_last4,
        bank_ifsc=vendor.bank_ifsc,
        commission_bps=vendor.commission_bps,
        approved_at=vendor.approved_at,
        rejection_reason=vendor.rejection_reason,
        suspension_reason=vendor.suspension_reason,
        can_publish=vendor.can_publish,
        can_receive_payouts=vendor.can_receive_payouts,
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=VendorResponse,
    summary="Apply to list properties",
)
async def register(
    body: RegisterVendorRequest,
    actor: ActorDep,
    use_case: Annotated[RegisterVendor, Depends(deps.register_vendor_uc)],
) -> VendorResponse:
    """Idempotent: applying twice returns the existing application rather than
    creating a second, which would make "which one gets paid?" ambiguous."""
    return _to_response(await use_case.execute(body.model_dump(), actor))


@router.get("/me", response_model=VendorResponse, summary="Your vendor account")
async def my_vendor(uow: deps.VendorUowDep, actor: ActorDep) -> VendorResponse:
    vendor = await uow.vendors.get_by_owner(actor.user_id)  # type: ignore[arg-type]
    if vendor is None:
        raise VendorNotFoundError
    return _to_response(vendor)


@router.put("/me/bank", response_model=VendorResponse, summary="Payout account")
async def update_bank(
    body: UpdateBankRequest, uow: deps.VendorUowDep, actor: ActorDep
) -> VendorResponse:
    vendor = await uow.vendors.get_by_owner(actor.user_id)  # type: ignore[arg-type]
    if vendor is None:
        raise VendorNotFoundError
    vendor.update_bank(last4=body.account_last4, ifsc=body.ifsc)
    return _to_response(vendor)


# ══════════════════════════════════════════════════════════════════════════
# Review
# ══════════════════════════════════════════════════════════════════════════


@admin_router.get(
    "/{vendor_id}",
    response_model=VendorResponse,
    dependencies=[CanApprove],
    summary="One vendor",
)
async def get_vendor(
    vendor_id: uuid.UUID, uow: deps.VendorUowDep, actor: ActorDep
) -> VendorResponse:
    vendor = await uow.vendors.get(vendor_id)
    if vendor is None:
        raise VendorNotFoundError
    return _to_response(vendor)


@admin_router.post(
    "/{vendor_id}/review",
    response_model=VendorResponse,
    dependencies=[CanApprove],
    summary="Claim for review",
)
async def begin_review(
    vendor_id: uuid.UUID,
    actor: ActorDep,
    use_case: Annotated[ReviewVendor, Depends(deps.review_vendor_uc)],
) -> VendorResponse:
    """Marks it as being worked on, so two reviewers do not duplicate the
    effort — and so "how long does approval take?" is answerable from data."""
    return _to_response(await use_case.begin_review(vendor_id, actor))


@admin_router.post(
    "/{vendor_id}/approve",
    response_model=VendorResponse,
    dependencies=[CanApprove],
    summary="Approve",
    responses={409: {"description": "No PAN on file"}},
)
async def approve(
    vendor_id: uuid.UUID,
    body: ApproveVendorRequest,
    actor: ActorDep,
    use_case: Annotated[ReviewVendor, Depends(deps.review_vendor_uc)],
) -> VendorResponse:
    """Authorises publishing **and** payouts.

    Refused without a PAN on file: it is what the platform files TDS against,
    and approving without it creates a payable finance cannot legally settle.
    """
    return _to_response(
        await use_case.approve(vendor_id, actor, commission_bps=body.commission_bps)
    )


@admin_router.post(
    "/{vendor_id}/reject",
    response_model=VendorResponse,
    dependencies=[CanApprove],
    summary="Reject",
)
async def reject(
    vendor_id: uuid.UUID,
    body: RejectVendorRequest,
    actor: ActorDep,
    use_case: Annotated[ReviewVendor, Depends(deps.review_vendor_uc)],
) -> VendorResponse:
    """A reason is required — a rejection the applicant cannot act on is one
    support cannot defend three months later."""
    return _to_response(await use_case.reject(vendor_id, body.reason, actor))


@admin_router.post(
    "/{vendor_id}/suspend",
    response_model=VendorResponse,
    dependencies=[CanApprove],
    summary="Suspend",
)
async def suspend(
    vendor_id: uuid.UUID,
    body: SuspendVendorRequest,
    actor: ActorDep,
    use_case: Annotated[ReviewVendor, Depends(deps.review_vendor_uc)],
) -> VendorResponse:
    """Stops new bookings and holds payouts. Deliberately does **not** cancel
    existing bookings — guests with a confirmed stay have a contract, and
    voiding it because the host is under investigation punishes the wrong
    party."""
    return _to_response(await use_case.suspend(vendor_id, body.reason, actor))


# ══════════════════════════════════════════════════════════════════════════
# Revenue and reports
# ══════════════════════════════════════════════════════════════════════════
#
# Every query below is scoped to the caller's own `vendor_id`, taken from the
# token and never from a parameter. A vendor cannot ask for another vendor's
# numbers because there is nowhere to put the request.


@router.get(
    "/dashboard",
    response_model=VendorDashboardResponse,
    summary="What needs doing, and how the month is going",
)
async def vendor_dashboard(
    queries: deps.VendorQueriesDep, actor: ActorDep
) -> VendorDashboardResponse:
    return VendorDashboardResponse(**dto_dict(await queries.dashboard(vendor_id=_vendor_of(actor))))


@router.get("/earnings", response_model=EarningsResponse, summary="Payout statement")
async def earnings(
    queries: deps.VendorQueriesDep,
    actor: ActorDep,
    from_date: date | None = None,
    to_date: date | None = None,
) -> EarningsResponse:
    """Gross, minus the platform's commission, minus refunds issued in the
    period, minus tax — leaving what will actually be transferred.

    Refunds land in the period they were *issued*, not the period the booking
    was made, because that is how the ledger and therefore the bank transfer
    work.
    """
    start, end = _window(from_date, to_date)
    return EarningsResponse(
        **dto_dict(
            await queries.earnings(vendor_id=_vendor_of(actor), from_date=start, to_date=end)
        ),
        from_date=start,
        to_date=end,
    )


@router.get(
    "/arrivals",
    response_model=list[ArrivalResponse],
    summary="Who is turning up",
)
async def arrivals(
    queries: deps.VendorQueriesDep,
    actor: ActorDep,
    days: Annotated[int, Query(ge=1, le=60)] = 14,
) -> list[ArrivalResponse]:
    """The one operational list a host reads every morning."""
    rows = await queries.upcoming_arrivals(vendor_id=_vendor_of(actor), days=days)
    return [ArrivalResponse(**dto_dict(row)) for row in rows]


@router.get("/reports", response_model=ReportsResponse, summary="Everything, for a period")
async def reports(
    queries: deps.VendorQueriesDep,
    actor: ActorDep,
    from_date: date | None = None,
    to_date: date | None = None,
) -> ReportsResponse:
    """Assembled server-side rather than by five parallel requests: the figures
    have to agree with each other, and five queries issued at slightly different
    moments do not."""
    vendor_id = _vendor_of(actor)
    start, end = _window(from_date, to_date)

    return ReportsResponse(
        earnings=EarningsResponse(
            **dto_dict(await queries.earnings(vendor_id=vendor_id, from_date=start, to_date=end)),
            from_date=start,
            to_date=end,
        ),
        occupancy=OccupancyResponse(
            **dto_dict(await queries.occupancy(vendor_id=vendor_id, from_date=start, to_date=end))
        ),
        by_property=[
            PropertyPerformanceResponse(**dto_dict(row))
            for row in await queries.by_property(vendor_id=vendor_id, from_date=start, to_date=end)
        ],
        monthly=[
            MonthlyStatementRow(**dto_dict(row))
            for row in await queries.monthly_statement(vendor_id=vendor_id)
        ],
        revenue_by_day=[
            RevenuePointResponse(**dto_dict(row))
            for row in await queries.revenue_by_day(
                vendor_id=vendor_id, days=min((end - start).days + 1, 90)
            )
        ],
    )


@router.get(
    "/reports/statement.csv",
    summary="Monthly statement as CSV",
    response_class=PlainTextResponse,
)
async def statement_csv(queries: deps.VendorQueriesDep, actor: ActorDep) -> PlainTextResponse:
    """A file an accountant can open.

    Amounts are written in **rupees with two decimals**, not minor units —
    everything internal is integer paise, but a spreadsheet a human reconciles
    against a bank statement should read the way the bank statement does.
    """
    rows = await queries.monthly_statement(vendor_id=_vendor_of(actor))
    lines = ["month,bookings,gross,commission,tax,net"]
    lines += [
        f"{row.month:%Y-%m},{row.bookings},"
        f"{row.gross_minor / 100:.2f},{row.commission_minor / 100:.2f},"
        f"{row.tax_minor / 100:.2f},{row.net_minor / 100:.2f}"
        for row in rows
    ]
    return PlainTextResponse(
        "\n".join(lines),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="statement.csv"'},
    )


def _vendor_of(actor: ActorDep) -> uuid.UUID:
    """The caller's own vendor id, from the token.

    Never a request parameter: a reporting endpoint that accepts a vendor id is
    one where a missing check shows a host someone else's revenue.
    """
    if actor.vendor_id is None:
        raise VendorNotFoundError
    return actor.vendor_id


def _window(from_date: date | None, to_date: date | None) -> tuple[date, date]:
    """Defaults to the last 30 days, clamped to a year.

    Clamped rather than rejected: a host who types a five-year range wants a
    report, and quietly narrowing it beats a validation error — but an
    unbounded aggregate over `bookings` is how a report takes the site down.
    """
    # `utcnow()`, not `date.today()`: the process may run in any timezone, and
    # the whole codebase measures time from one clock so a report and a booking
    # cannot disagree about what day it is.
    end = to_date or utcnow().date()
    start = from_date or (end - timedelta(days=29))
    if (end - start).days > 365:
        start = end - timedelta(days=365)
    return start, end
