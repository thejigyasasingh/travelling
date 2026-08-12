"""Wishlist request and response shapes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.modules.wishlist.application.use_cases import MAX_MERGE
from app.modules.wishlist.infrastructure.models import MAX_NOTE


class SaveRequest(BaseModel):
    note: Annotated[str, Field(max_length=MAX_NOTE)] = ""


class MergeRequest(BaseModel):
    """The device's local list, handed over at sign-in."""

    property_ids: Annotated[list[uuid.UUID], Field(max_length=MAX_MERGE)]


class SavedPropertyResponse(BaseModel):
    property_id: uuid.UUID
    name: str
    slug: str
    city: str
    country_code: str
    currency: str
    cover_image_url: str | None = None
    #: Read live, never stored. Null for a listing that is no longer on sale —
    #: a price on something nobody can book is a support ticket waiting.
    from_price_minor: int | None = None
    review_average: float
    review_count: int
    #: False means the listing has been taken down. The client renders a
    #: tombstone rather than dropping the row, so the guest sees what they lost.
    available: bool
    note: str | None = None
    saved_at: datetime


class MergeResponse(BaseModel):
    merged: int
