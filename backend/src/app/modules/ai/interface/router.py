"""AI endpoints.

Grouped by who they are for: guests get recommendations, itineraries and the
assistant; hosts get image descriptions for their own listings; staff get the
attention queue.

Two things hold across every route here.

**Anonymous is allowed, metered is mandatory.** Recommendations and the
assistant work signed out, because a first-time visitor is exactly who they are
for. Every route that reaches a model consumes budget first, and anonymous
callers share one bucket.

**Nothing degrades into an error page.** A model outage produces recommendations
without explanations and a 503 with a plain sentence on the two features that
genuinely cannot work without it. Search, browse and booking are untouched.
"""

from __future__ import annotations

import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.interface.api.deps import ActorDep, ContainerDep, OptionalActorDep
from app.modules.ai.application.use_cases.chat import ChatTurn, new_conversation_id, to_public
from app.modules.ai.application.use_cases.itinerary import (
    ItineraryRequest,
    plan_to_json,
)
from app.modules.ai.application.use_cases.recommend import (
    RecommendForYou,
    RecommendSimilar,
    SuggestDestinations,
)
from app.modules.ai.domain.value_objects import Recommendation
from app.modules.ai.infrastructure.budget import Feature, Period
from app.modules.ai.interface import deps
from app.modules.ai.interface.schemas import (
    AttentionItem,
    AttentionQueueResponse,
    ChatRequestBody,
    ChatResponse,
    DestinationsResponse,
    DestinationSuggestion,
    ImageAnnotationResponse,
    ItineraryRequestBody,
    ItineraryResponse,
    PropertySentimentResponse,
    RecommendationsResponse,
    RecommendedProperty,
    ReviewInsightResponse,
    TagImagesResponse,
)
from app.modules.auth.domain.rbac import Permission
from app.modules.auth.interface.permissions import RequirePermission

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])
vendor_router = APIRouter(prefix="/vendor/ai", tags=["vendor: ai"])
admin_router = APIRouter(prefix="/admin/ai", tags=["admin: ai"])

CanModerate = Depends(RequirePermission(Permission.REVIEW_MODERATE_ANY))

#: An aspect has to appear this often before it is called a pattern. One guest
#: mentioning noise is a data point; five is something a host should know.
PATTERN_THRESHOLD = 3


def _to_response(recommendation: Recommendation) -> RecommendedProperty:
    candidate = recommendation.candidate
    return RecommendedProperty(
        property_id=candidate.property_id,
        name=candidate.name,
        city=candidate.city,
        property_type=candidate.property_type,
        # Withheld below the confidence threshold rather than sent with a
        # caveat a client may not render.
        review_average=round(candidate.review_average, 1) if candidate.is_rated else None,
        review_count=candidate.review_count,
        source=recommendation.source.value,
        reason=recommendation.reason,
        score=recommendation.score,
    )


def _wrap(items: list[Recommendation]) -> RecommendationsResponse:
    return RecommendationsResponse(
        items=[_to_response(item) for item in items],
        explanations_available=any(item.reason for item in items),
    )


# ══════════════════════════════════════════════════════════════════════════
# Recommendations — no budget check, because no model call is required
# ══════════════════════════════════════════════════════════════════════════


@router.get(
    "/properties/{property_id}/similar",
    response_model=RecommendationsResponse,
    summary="More like this",
)
async def similar(
    property_id: uuid.UUID,
    use_case: Annotated[RecommendSimilar, Depends(deps.similar_uc)],
    limit: Annotated[int, Query(ge=1, le=24)] = 8,
) -> RecommendationsResponse:
    """Blends co-booking with attribute similarity.

    Unmetered and anonymous: the ranking is SQL, and the optional explanation
    runs on the cheap model against at most six candidates. Rate limiting is
    the middleware's job here, not the budget's.
    """
    return _wrap(await use_case.execute(property_id, limit=limit))


@router.get("/for-you", response_model=RecommendationsResponse, summary="Picked for you")
async def for_you(
    actor: OptionalActorDep,
    use_case: Annotated[RecommendForYou, Depends(deps.for_you_uc)],
    city: Annotated[str, Query(max_length=80)] = "",
    limit: Annotated[int, Query(ge=1, le=24)] = 12,
) -> RecommendationsResponse:
    """Personalised where there is history to personalise from, popular where
    there is not — and the `source` on each item says which."""
    return _wrap(await use_case.execute(actor, city=city, limit=limit))


@router.get("/destinations", response_model=DestinationsResponse, summary="Where to go next")
async def destinations(
    actor: OptionalActorDep,
    budget: deps.BudgetDep,
    container: ContainerDep,
    use_case: Annotated[SuggestDestinations, Depends(deps.destinations_uc)],
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
) -> DestinationsResponse:
    """The one recommendation surface where the model chooses.

    It chooses from cities we have supply in, so a manipulated ranking is a
    badly ordered list of bookable places rather than an advert for a
    competitor.
    """
    await budget.consume(
        user_id=actor.user_id,
        feature=Feature.DESTINATIONS,
        limit=container.settings.ai.itineraries_per_user_per_day,
        period=Period.DAY,
    )
    items = await use_case.execute(actor, month=utcnow().strftime("%B"), limit=limit)
    return DestinationsResponse(
        items=[
            DestinationSuggestion(
                city=item["city"],
                reason=item.get("reason"),
                best_months=item.get("best_months", []),
            )
            for item in items
        ],
        generic=all(item.get("generic", False) for item in items) if items else True,
    )


# ══════════════════════════════════════════════════════════════════════════
# Itineraries
# ══════════════════════════════════════════════════════════════════════════


@router.post(
    "/itinerary",
    response_model=ItineraryResponse,
    summary="Plan a trip",
    status_code=status.HTTP_200_OK,
)
async def itinerary(
    body: ItineraryRequestBody,
    actor: OptionalActorDep,
    uow: deps.AIUowDep,
    budget: deps.BudgetDep,
    container: ContainerDep,
    use_case: Annotated[object, Depends(deps.itinerary_uc)],
) -> ItineraryResponse:
    """POST rather than GET despite being a read.

    The request has four fields including free text, and it is expensive
    enough that it must not be issued by a link preview or a crawler
    following a URL.

    Cached on the request, not the requester: two guests asking for four days
    in Goa share one generation.
    """
    from app.modules.ai.application.use_cases.itinerary import GenerateItinerary

    assert isinstance(use_case, GenerateItinerary)
    request = ItineraryRequest(
        city=body.city, days=body.days, travellers=body.travellers, interests=body.interests
    )

    # The cache is checked before the budget. A cached plan costs nothing, and
    # charging for it would make a popular question progressively harder to
    # ask.
    cached = await uow.store.cached_itinerary(GenerateItinerary._cache_key(request))
    if cached is None:
        await budget.consume(
            user_id=actor.user_id,
            feature=Feature.ITINERARY,
            limit=container.settings.ai.itineraries_per_user_per_day,
            period=Period.DAY,
        )

    started = time.monotonic()
    succeeded = False
    try:
        plan, key, generated = await use_case.execute(request, cached=cached)
        succeeded = True
    finally:
        if cached is None:
            await uow.store.record_usage(
                user_id=actor.user_id,
                feature=Feature.ITINERARY.value,
                model=container.settings.ai.model,
                latency_ms=int((time.monotonic() - started) * 1000),
                succeeded=succeeded,
            )

    if generated:
        await uow.store.save_itinerary(
            request_hash=key,
            city=request.city,
            days=request.days,
            summary=plan.summary,
            plan=plan_to_json(plan),
            referenced=list(plan.referenced_property_ids),
            low_confidence=plan.low_confidence,
            model=container.settings.ai.model,
            expires_at=use_case.expires_at(),
        )
    await uow.commit()

    return ItineraryResponse(
        city=plan.city,
        summary=plan.summary,
        days=[
            {
                "day": day.day,
                "title": day.title,
                "note": day.note,
                "items": [
                    {
                        "time_of_day": item.time_of_day,
                        "title": item.title,
                        "description": item.description,
                        "duration_minutes": item.duration_minutes,
                        "property_id": item.property_id,
                    }
                    for item in day.items
                ],
            }
            for day in plan.days
        ],
        referenced_property_ids=list(plan.referenced_property_ids),
        low_confidence=plan.low_confidence,
        generated=generated,
    )


# ══════════════════════════════════════════════════════════════════════════
# Assistant
# ══════════════════════════════════════════════════════════════════════════


@router.post("/chat", response_model=ChatResponse, summary="Ask the travel assistant")
async def chat(
    body: ChatRequestBody,
    actor: OptionalActorDep,
    uow: deps.AIUowDep,
    budget: deps.BudgetDep,
    container: ContainerDep,
    use_case: Annotated[object, Depends(deps.chat_uc)],
) -> ChatResponse:
    """One turn.

    The thread is loaded scoped to its owner, so a guessed conversation id
    reads an empty history rather than someone else's.
    """
    from app.modules.ai.application.use_cases.chat import Chat

    assert isinstance(use_case, Chat)

    await budget.consume(
        user_id=actor.user_id,
        feature=Feature.CHAT,
        limit=container.settings.ai.chat_messages_per_user_per_hour,
        period=Period.HOUR,
    )

    conversation_id = body.conversation_id or new_conversation_id()
    history = [
        ChatTurn(role=row["role"], content=row["content"])
        for row in await uow.store.conversation(conversation_id, user_id=actor.user_id)
    ]

    started = time.monotonic()
    succeeded = False
    try:
        reply = await use_case.execute(body.message, history=history, city_hint=body.city)
        succeeded = True
    finally:
        await uow.store.record_usage(
            user_id=actor.user_id,
            feature=Feature.CHAT.value,
            model=container.settings.ai.model,
            latency_ms=int((time.monotonic() - started) * 1000),
            succeeded=succeeded,
        )

    # The guest's message is stored after a successful reply, not before. A
    # failed turn leaves no trace, so a retry sees the same history rather
    # than a thread containing an unanswered question.
    await uow.store.append_message(
        conversation_id=conversation_id,
        user_id=actor.user_id,
        role="guest",
        content=body.message,
    )
    await uow.store.append_message(
        conversation_id=conversation_id,
        user_id=actor.user_id,
        role="assistant",
        content=reply.reply,
        suggested=[c.property_id for c in reply.suggested],
        needs_human=reply.needs_human,
    )
    await uow.commit()

    return ChatResponse(
        conversation_id=conversation_id,
        reply=reply.reply,
        suggestions=to_public(reply.suggested),
        follow_ups=list(reply.follow_ups),
        needs_human=reply.needs_human,
    )


# ══════════════════════════════════════════════════════════════════════════
# Sentiment — read-only, derived, public
# ══════════════════════════════════════════════════════════════════════════


@router.get(
    "/properties/{property_id}/sentiment",
    response_model=PropertySentimentResponse,
    summary="What guests consistently say",
)
async def sentiment(property_id: uuid.UUID, uow: deps.AIUowDep) -> PropertySentimentResponse:
    """The aggregate, not individual opinions.

    `praised` and `criticised` are derived from the tallies here rather than
    written by a model — the model's job was classifying one review at a time,
    and the pattern across them is arithmetic.
    """
    data = await uow.store.sentiment_for(property_id)
    if data is None:
        return PropertySentimentResponse(
            analysed_count=0, positive_count=0, mixed_count=0, negative_count=0
        )

    tallies = data["aspects"]
    aspects = [
        {
            "aspect": name,
            "positive": int(counts.get("positive", 0)),
            "negative": int(counts.get("negative", 0)),
        }
        for name, counts in sorted(tallies.items())
    ]
    return PropertySentimentResponse(
        analysed_count=data["analysed_count"],
        positive_count=data["positive_count"],
        mixed_count=data["mixed_count"],
        negative_count=data["negative_count"],
        aspects=aspects,
        praised=[a["aspect"] for a in aspects if a["positive"] >= PATTERN_THRESHOLD],
        criticised=[a["aspect"] for a in aspects if a["negative"] >= PATTERN_THRESHOLD],
    )


@router.get(
    "/properties/{property_id}/review-insights",
    response_model=list[ReviewInsightResponse],
    summary="Per-review summaries",
)
async def review_insights(
    property_id: uuid.UUID,
    uow: deps.AIUowDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[ReviewInsightResponse]:
    rows = await uow.store.insights_for(property_id, limit=limit)
    return [ReviewInsightResponse(**row) for row in rows]


# ══════════════════════════════════════════════════════════════════════════
# Image tagging — the host's own listings only
# ══════════════════════════════════════════════════════════════════════════


@vendor_router.post(
    "/properties/{property_id}/describe-images",
    response_model=TagImagesResponse,
    summary="Describe my photographs",
)
async def describe_images(
    property_id: uuid.UUID, actor: ActorDep, uow: deps.AIUowDep
) -> TagImagesResponse:
    """Queue every image on one of the host's own properties.

    Explicitly requested rather than automatic on upload. A host uploading
    twelve photographs should not silently trigger twelve vision calls, and
    the results are suggestions they have to act on anyway.

    Scoped by `vendor_id` in the query, so a property id belonging to another
    host queues nothing and reports nothing — 404, not 403.
    """
    from sqlalchemy import text

    from app.modules.ai.infrastructure.tasks import tag_image

    rows = (
        await uow.session.execute(
            text("""
            SELECT i.id
              FROM property_images i
              JOIN properties p ON p.id = i.property_id
             WHERE i.property_id = :pid AND p.vendor_id = :vid AND p.deleted_at IS NULL
            """),
            {"pid": property_id, "vid": actor.vendor_id},
        )
    ).all()

    for row in rows:
        tag_image.delay(aggregate_id=str(property_id), payload={"image_id": str(row[0])})

    logger.info("image_tagging_queued", property_id=str(property_id), images=len(rows))
    return TagImagesResponse(queued=len(rows))


@vendor_router.get(
    "/properties/{property_id}/image-annotations",
    response_model=list[ImageAnnotationResponse],
    summary="What the model saw",
)
async def image_annotations(
    property_id: uuid.UUID, actor: ActorDep, uow: deps.AIUowDep
) -> list[ImageAnnotationResponse]:
    from sqlalchemy import text

    owns = (
        await uow.session.execute(
            text("SELECT 1 FROM properties WHERE id = :pid AND vendor_id = :vid"),
            {"pid": property_id, "vid": actor.vendor_id},
        )
    ).first()
    if owns is None:
        return []

    rows = await uow.store.annotations_for(property_id)
    return [ImageAnnotationResponse(**row) for row in rows]


# ══════════════════════════════════════════════════════════════════════════
# Staff
# ══════════════════════════════════════════════════════════════════════════


@admin_router.get(
    "/attention",
    response_model=AttentionQueueResponse,
    dependencies=[CanModerate],
    summary="Reviews the analysis flagged",
)
async def attention_queue(
    uow: deps.AIUowDep, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> AttentionQueueResponse:
    """Reviews describing a safety problem, a discrimination complaint, or a
    billing dispute.

    Advisory. Nothing here is hidden from guests and nothing is acted on
    automatically — the queue exists so a person sees it within hours instead
    of when the guest escalates.
    """
    rows = await uow.store.attention_queue(limit=limit)
    return AttentionQueueResponse(items=[AttentionItem(**row) for row in rows])


@admin_router.post(
    "/attention/{insight_id}/acknowledge",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[CanModerate],
    summary="Mark as seen",
)
async def acknowledge(insight_id: uuid.UUID, uow: deps.AIUowDep) -> None:
    await uow.store.acknowledge(insight_id)
    await uow.commit()
