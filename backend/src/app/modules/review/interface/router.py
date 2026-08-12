"""Review endpoints.

Three audiences: a guest writing about their stay, a host answering, and staff
moderating. The permissions come from the RBAC catalogue that has carried
`review:*` since Phase 5.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.interface.api.deps import ActorDep, OptionalActorDep
from app.modules.auth.domain.rbac import Permission
from app.modules.auth.interface.permissions import RequirePermission
from app.modules.review.application.dto import ReviewDraft
from app.modules.review.application.use_cases import (
    EditReview,
    FlagReview,
    ModerateReview,
    ReplyToReview,
    WriteReview,
)
from app.modules.review.domain.entities import Review
from app.modules.review.interface import deps
from app.modules.review.interface.schemas import (
    EditReviewRequest,
    FlagRequest,
    ModerateRequest,
    ReplyRequest,
    ReviewListResponse,
    ReviewResponse,
    VendorReviewSummaryResponse,
    WriteReviewRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/reviews", tags=["reviews"])
vendor_router = APIRouter(prefix="/vendor/reviews", tags=["vendor: reviews"])
admin_router = APIRouter(prefix="/admin/reviews", tags=["admin: reviews"])

CanModerate = Depends(RequirePermission(Permission.REVIEW_MODERATE_ANY))
CanRespond = Depends(RequirePermission(Permission.REVIEW_RESPOND_VENDOR))


def _to_response(review: Review, *, editable: bool = False) -> ReviewResponse:
    return ReviewResponse(
        id=review.id,
        property_id=review.property_id,
        rating=int(review.rating),
        title=review.title,
        body=review.body,
        categories=review.categories,
        author_name=review.author_name,
        published_at=review.created_at,
        edited_at=review.edited_at,
        host_reply=review.host_reply,
        host_replied_at=review.host_replied_at,
        moderation=review.moderation.value,
        can_edit=editable and review.can_edit(utcnow()),
    )


# ══════════════════════════════════════════════════════════════════════════
# Public
# ══════════════════════════════════════════════════════════════════════════


@router.get(
    "/property/{property_id}",
    response_model=ReviewListResponse,
    summary="Reviews for a property",
)
async def list_for_property(
    property_id: uuid.UUID,
    uow: deps.ReviewUowDep,
    actor: OptionalActorDep,
    sort: Annotated[str, Query(pattern="^(recent|rating_desc|rating_asc)$")] = "recent",
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ReviewListResponse:
    """Public. Removed reviews are absent; flagged ones are present.

    A host who could hide criticism by objecting to it would make every rating
    on the platform meaningless, so flagging is visible to staff and invisible
    to readers.
    """
    reviews, total = await uow.reviews.list_for_property(
        property_id, limit=size, offset=(page - 1) * size, sort=sort
    )
    summary = await uow.reviews.summary(property_id)
    return ReviewListResponse(
        items=[
            _to_response(r, editable=actor.user_id is not None and r.author_id == actor.user_id)
            for r in reviews
        ],
        total=total,
        page=page,
        size=size,
        average=float(summary["average"]) if summary else 0.0,
        distribution=dict(summary["distribution"]) if summary else {},
    )


@router.get(
    "/mine",
    response_model=list[ReviewResponse],
    summary="Reviews you have written",
)
async def list_mine(uow: deps.ReviewUowDep, actor: ActorDep) -> list[ReviewResponse]:
    """A guest's own reviews, including any staff removed.

    The author is the one person entitled to know their review was taken down.
    Learning it only from its absence on a property page is how a moderation
    decision turns into a support ticket, so `moderation` is returned as-is and
    the client says so.

    Declared before `/{review_id}` would be — FastAPI matches in declaration
    order, and a later literal route loses to an earlier parameterised one.
    """
    if actor.user_id is None:  # pragma: no cover — ActorDep already guarantees it
        return []
    reviews = await uow.reviews.list_for_author(actor.user_id)
    now = utcnow()
    return [_to_response(review, editable=review.can_edit(now)) for review in reviews]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ReviewResponse,
    summary="Review a completed stay",
    responses={
        404: {"description": "No such booking of yours"},
        409: {"description": "Stay is not complete, already reviewed, or too long ago"},
    },
)
async def write_review(
    body: WriteReviewRequest,
    actor: ActorDep,
    use_case: Annotated[WriteReview, Depends(deps.write_review_uc)],
) -> ReviewResponse:
    """Takes a **booking id**, not a property id.

    That is the whole integrity model: the booking proves the author stayed
    there, one booking yields one review, and a guest cannot review a property
    they never visited by guessing its id.
    """
    review = await use_case.execute(
        ReviewDraft(
            booking_id=body.booking_id,
            rating=body.rating,
            body=body.body,
            title=body.title,
            categories=body.categories,
        ),
        actor,
    )
    return _to_response(review, editable=True)


@router.patch("/{review_id}", response_model=ReviewResponse, summary="Correct your review")
async def edit_review(
    review_id: uuid.UUID,
    body: EditReviewRequest,
    actor: ActorDep,
    use_case: Annotated[EditReview, Depends(deps.edit_review_uc)],
) -> ReviewResponse:
    """Open for 48 hours, and closed the moment the host replies — rewriting a
    review under an answer that addressed the original makes a host look
    evasive."""
    review = await use_case.execute(
        review_id,
        ReviewDraft(
            booking_id=uuid.UUID(int=0),  # unused on edit
            rating=body.rating or 0,
            body=body.body or "",
            title=body.title,
            categories=body.categories or {},
        ),
        actor,
    )
    return _to_response(review, editable=True)


# ══════════════════════════════════════════════════════════════════════════
# Vendor
# ══════════════════════════════════════════════════════════════════════════


@vendor_router.get("", response_model=ReviewListResponse, summary="Your reviews")
async def vendor_reviews(
    uow: deps.ReviewUowDep,
    actor: ActorDep,
    awaiting_reply: bool = False,
    property_id: uuid.UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ReviewListResponse:
    if actor.vendor_id is None:
        return ReviewListResponse(items=[], total=0, page=page, size=size)

    reviews, total = await uow.reviews.list_for_vendor(
        actor.vendor_id,
        awaiting_reply=awaiting_reply,
        property_id=property_id,
        limit=size,
        offset=(page - 1) * size,
    )
    return ReviewListResponse(
        items=[_to_response(r) for r in reviews], total=total, page=page, size=size
    )


@vendor_router.get(
    "/summary",
    response_model=VendorReviewSummaryResponse,
    summary="Rating and what needs answering",
)
async def vendor_review_summary(
    uow: deps.ReviewUowDep, actor: ActorDep
) -> VendorReviewSummaryResponse:
    if actor.vendor_id is None:
        return VendorReviewSummaryResponse(total=0, average=0, awaiting_reply=0, critical=0)
    return VendorReviewSummaryResponse(**await uow.reviews.vendor_summary(actor.vendor_id))


@vendor_router.post(
    "/{review_id}/reply",
    response_model=ReviewResponse,
    dependencies=[CanRespond],
    summary="Answer a review",
)
async def reply(
    review_id: uuid.UUID,
    body: ReplyRequest,
    actor: ActorDep,
    use_case: Annotated[ReplyToReview, Depends(deps.reply_uc)],
) -> ReviewResponse:
    """One reply, not a thread. A review page that becomes an argument helps
    nobody reading it."""
    return _to_response(await use_case.execute(review_id, body.body, actor))


@vendor_router.post(
    "/{review_id}/flag",
    response_model=ReviewResponse,
    dependencies=[CanRespond],
    summary="Dispute a review",
)
async def flag(
    review_id: uuid.UUID,
    body: FlagRequest,
    actor: ActorDep,
    use_case: Annotated[FlagReview, Depends(deps.flag_uc)],
) -> ReviewResponse:
    """Raises it with staff. Deliberately does **not** hide the review or stop
    it counting — otherwise a host could suppress criticism by objecting to
    it."""
    return _to_response(await use_case.execute(review_id, body.reason, actor))


# ══════════════════════════════════════════════════════════════════════════
# Moderation
# ══════════════════════════════════════════════════════════════════════════


@admin_router.post(
    "/{review_id}/moderate",
    response_model=ReviewResponse,
    dependencies=[CanModerate],
    summary="Remove or restore a review",
)
async def moderate(
    review_id: uuid.UUID,
    body: ModerateRequest,
    actor: ActorDep,
    use_case: Annotated[ModerateReview, Depends(deps.moderate_uc)],
) -> ReviewResponse:
    """For personal data, threats or a review of the wrong property — not for
    being negative. The reason is recorded and the rating is recomputed."""
    return _to_response(
        await use_case.execute(review_id, remove=body.remove, reason=body.reason, actor=actor)
    )
