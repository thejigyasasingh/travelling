"""Review HTTP schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WriteReviewRequest(BaseModel):
    #: The booking, not the property. The booking is the evidence that the
    #: author stayed there.
    booking_id: uuid.UUID
    rating: int = Field(ge=1, le=5)
    body: str = Field(min_length=40, max_length=4000)
    title: str | None = Field(default=None, max_length=120)
    #: Per-category sub-scores, each 1 to 5. Unknown keys are dropped rather than
    #: rejected, so a newer client still produces a review.
    categories: dict[str, int] = Field(default_factory=dict)


class EditReviewRequest(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    body: str | None = Field(default=None, min_length=40, max_length=4000)
    title: str | None = Field(default=None, max_length=120)
    categories: dict[str, int] | None = None


class ReplyRequest(BaseModel):
    body: str = Field(min_length=10, max_length=4000)


class FlagRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ModerateRequest(BaseModel):
    remove: bool
    reason: str = Field(min_length=3, max_length=500)


class ReviewResponse(BaseModel):
    id: uuid.UUID
    property_id: uuid.UUID
    rating: int
    title: str | None = None
    body: str
    categories: dict[str, int] = Field(default_factory=dict)
    author_name: str
    published_at: datetime
    edited_at: datetime | None = None
    host_reply: str | None = None
    host_replied_at: datetime | None = None
    #: Flagged reviews are still shown and still counted — see `Review.flag`.
    moderation: str
    can_edit: bool = False


class ReviewListResponse(BaseModel):
    items: list[ReviewResponse]
    total: int
    page: int
    size: int
    average: float = 0
    distribution: dict[int, int] = Field(default_factory=dict)


class VendorReviewSummaryResponse(BaseModel):
    total: int
    average: float
    awaiting_reply: int
    #: Ratings of 1 or 2. Surfaced separately because they are the ones a host
    #: should answer today.
    critical: int
