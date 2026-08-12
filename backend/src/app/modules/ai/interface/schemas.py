"""Request and response shapes for the AI endpoints.

Two conventions run through all of them.

**Every AI-generated field is nullable, and clients are expected to render
without it.** `reason`, `summary`, `alt_text` — each is absent when the model
was unavailable, and a client that treats any of them as required will show an
empty box during an outage rather than degrading.

**Nothing here carries a price.** Recommendations and assistant replies deal in
identity and attributes; the price a guest is quoted comes from the property
and quote endpoints, which compute it. A number that has travelled through a
language model is not a number to put next to a currency symbol.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

# ══════════════════════════════════════════════════════════════════════════
# Recommendations
# ══════════════════════════════════════════════════════════════════════════


class RecommendedProperty(BaseModel):
    property_id: uuid.UUID
    name: str
    city: str
    property_type: str
    #: Null below three reviews. An average over one or two is an anecdote,
    #: and rendering it as a rating invites a guest to weigh it as one.
    review_average: float | None = None
    review_count: int
    #: Why this was shown. Rendered as the "because …" line, so a guest can
    #: account for a recommendation instead of assuming it was bought.
    source: Literal["also_booked", "similar", "your_history", "popular", "nearby"]
    #: The model's sentence. Null whenever the model was unavailable.
    reason: str | None = None
    #: Exposed for debugging and for evaluating a ranking change. Not shown to
    #: guests; a score next to a hotel invites arguments nobody can settle.
    score: float


class RecommendationsResponse(BaseModel):
    items: list[RecommendedProperty]
    #: True when the explanations are missing because the model was
    #: unavailable, so a client can hide the copy rather than show gaps.
    explanations_available: bool


class DestinationSuggestion(BaseModel):
    city: str
    reason: str | None = None
    best_months: list[str] = Field(default_factory=list)


class DestinationsResponse(BaseModel):
    items: list[DestinationSuggestion]
    #: True when there was not enough history to personalise. Stated rather
    #: than hidden — a generic list presented as "picked for you" is a small
    #: lie that gets found out the first time two people compare screens.
    generic: bool


# ══════════════════════════════════════════════════════════════════════════
# Itineraries
# ══════════════════════════════════════════════════════════════════════════


class ItineraryRequestBody(BaseModel):
    city: Annotated[str, Field(min_length=2, max_length=80)]
    days: Annotated[int, Field(ge=1, le=21)]
    travellers: Annotated[str, Field(max_length=40)] = "any"
    #: The only free-text input. Short by design: long enough for "travelling
    #: with a toddler, no long drives", too short to carry an instruction
    #: frame — and it participates in the cache key, so it must not contain
    #: anything identifying.
    interests: Annotated[str, Field(max_length=300)] = ""


class ItineraryItemResponse(BaseModel):
    time_of_day: str
    title: str
    description: str
    duration_minutes: int | None = None
    #: Present only where the item is a place to stay that exists in our
    #: catalogue. Everything else is a suggestion with no link, because a
    #: bookable link to a beach is a bug.
    property_id: uuid.UUID | None = None


class ItineraryDayResponse(BaseModel):
    day: int
    title: str
    note: str | None = None
    items: list[ItineraryItemResponse]


class ItineraryResponse(BaseModel):
    city: str
    summary: str
    days: list[ItineraryDayResponse]
    referenced_property_ids: list[uuid.UUID] = Field(default_factory=list)
    #: The model's own admission of uncertainty, passed straight through.
    low_confidence: bool = False
    #: Whether this was generated now or reused. Surfaced so a client can
    #: explain a slow first request, and so cache behaviour is observable
    #: without reading server logs.
    generated: bool
    #: Stated on every response. A plan is a starting point, and the platform
    #: is not the source of truth for opening hours or ticket prices.
    disclaimer: str = "Generated suggestions. Check opening times and prices before you travel."


# ══════════════════════════════════════════════════════════════════════════
# Chat
# ══════════════════════════════════════════════════════════════════════════


class ChatRequestBody(BaseModel):
    message: Annotated[str, Field(min_length=1, max_length=1000)]
    #: Omitted on the first message; echoed back and reused afterwards.
    conversation_id: uuid.UUID | None = None
    city: Annotated[str, Field(max_length=80)] = ""


class ChatSuggestion(BaseModel):
    property_id: uuid.UUID
    name: str
    city: str
    property_type: str
    review_average: float | None = None
    review_count: int


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    reply: str
    suggestions: list[ChatSuggestion] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    #: The assistant handing over. Clients show a route to support rather than
    #: inviting another message into a conversation that cannot help.
    needs_human: bool = False


# ══════════════════════════════════════════════════════════════════════════
# Sentiment
# ══════════════════════════════════════════════════════════════════════════


class AspectTally(BaseModel):
    aspect: str
    positive: int
    negative: int


class PropertySentimentResponse(BaseModel):
    #: How many reviews have been analysed — not how many exist. The two
    #: differ during a backlog and after an outage, and a client showing
    #: "based on 40 reviews" when 12 were analysed is misreporting.
    analysed_count: int
    positive_count: int
    mixed_count: int
    negative_count: int
    aspects: list[AspectTally] = Field(default_factory=list)
    #: What guests consistently praise and consistently criticise, derived
    #: from the tallies rather than written by a model.
    praised: list[str] = Field(default_factory=list)
    criticised: list[str] = Field(default_factory=list)


class ReviewInsightResponse(BaseModel):
    review_id: uuid.UUID
    sentiment: str
    summary: str
    aspects: list[dict[str, Any]] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════
# Image tagging
# ══════════════════════════════════════════════════════════════════════════


class ImageAnnotationResponse(BaseModel):
    image_id: uuid.UUID
    #: The accessibility deliverable. Every property image on the platform
    #: ships without one otherwise.
    alt_text: str
    tags: list[dict[str, Any]] = Field(default_factory=list)
    #: Suggestions for the host to confirm. Never applied to a listing
    #: automatically — a model that sees a hot tub in a neighbour's garden
    #: must not add one to somebody's amenities.
    suggested_amenities: list[str] = Field(default_factory=list)
    flagged: bool = False
    flag_reason: str | None = None
    reviewed: bool = False


class TagImagesResponse(BaseModel):
    queued: int
    #: Named so a host understands nothing has happened yet.
    detail: str = "Photographs are being described. Check back in a few minutes."


# ══════════════════════════════════════════════════════════════════════════
# Moderation queue
# ══════════════════════════════════════════════════════════════════════════


class AttentionItem(BaseModel):
    id: uuid.UUID
    review_id: uuid.UUID
    property_id: uuid.UUID
    property_name: str
    reason: str | None = None
    summary: str


class AttentionQueueResponse(BaseModel):
    items: list[AttentionItem]
    #: Stated on the response because the queue is advisory: a model's opinion
    #: that something needs a human is a prompt to look, not a finding.
    note: str = "Flagged by automated analysis. Each item needs a human decision."
