"""Tables owned by the AI module.

Everything here is *derived* data. Every row can be deleted and regenerated,
and nothing else in the platform depends on one existing — which is the
property that lets a model change, a prompt rewrite, or a bad batch be fixed by
truncating a table rather than by a migration with a data backfill.

Each table carries a ``content_hash`` and a ``model`` column. Together they
answer the two questions that come up constantly with generated data: "is this
still current?" and "which model wrote it?". Without the first, an edited
review keeps its old sentiment forever. Without the second, a regression after
a model upgrade cannot be scoped to the rows it affected.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ReviewInsightModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The analysis of one review.

    One row per review, replaced when the review is edited. A separate table
    rather than columns on ``reviews`` for a specific reason: the review module
    must not depend on the AI module. A review is a fact a guest wrote; its
    sentiment is a guess we made about it, and mixing the two puts a
    third-party model's output inside the aggregate that guest owns.
    """

    __tablename__ = "review_insights"

    review_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    #: Denormalised so the per-property aggregate does not join reviews. This
    #: table is read on every property page; that join is not worth paying.
    property_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )

    sentiment: Mapped[str] = mapped_column(String(10), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    #: ``[{"aspect": "cleanliness", "score": 1, "quote": "…"}, …]``
    aspects: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    #: Flattened for querying. Filtering "reviews mentioning noise" through a
    #: JSONB containment check is possible; through an indexed array it is fast.
    positive_aspects: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)), nullable=False, server_default=text("'{}'::varchar[]")
    )
    negative_aspects: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)), nullable=False, server_default=text("'{}'::varchar[]")
    )

    needs_attention: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    attention_reason: Mapped[str | None] = mapped_column(String(200))
    #: Cleared when support has looked. Nullable rather than a boolean so the
    #: audit answers "when", not just "yes".
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    model: Mapped[str] = mapped_column(String(60), nullable=False)
    #: SHA-256 of the analysed text. An edit changes it, which is what triggers
    #: re-analysis; an unchanged review re-delivered by the at-least-once
    #: outbox matches and costs nothing.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        # One insight per review. Makes the writer an idempotent upsert rather
        # than a check-then-insert, which is what at-least-once delivery needs.
        UniqueConstraint("review_id", name="uq_review_insights_review"),
        Index("ix_review_insights_property", "property_id"),
        # The support queue: unacknowledged, flagged. Partial, because the rows
        # that matter are a vanishing fraction of the table.
        Index(
            "ix_review_insights_attention",
            "created_at",
            postgresql_where=text("needs_attention AND acknowledged_at IS NULL"),
        ),
        Index("ix_review_insights_negative", "negative_aspects", postgresql_using="gin"),
    )


class PropertySentimentModel(Base, TimestampMixin):
    """Per-property aggregate of the above.

    Maintained incrementally as insights land, in the same transaction, for
    the same reason the rating summary is: recomputing across every review of a
    well-reviewed property on every write makes success expensive.
    """

    __tablename__ = "property_sentiment"

    property_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        primary_key=True,
    )
    analysed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    positive_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    mixed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    negative_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    #: ``{"cleanliness": {"positive": 12, "negative": 1}, …}``
    aspect_tallies: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class ImageAnnotationModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """What a vision model saw in one property photograph."""

    __tablename__ = "image_annotations"

    image_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("property_images.id", ondelete="CASCADE"),
        nullable=False,
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )

    alt_text: Mapped[str] = mapped_column(String(250), nullable=False)
    #: ``[{"label": "pool", "kind": "scene", "confidence": 0.94}, …]``
    tags: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    #: Intersected with the real amenity catalogue before storing. A
    #: **suggestion** — the host confirms it. A model that sees a hot tub in a
    #: neighbour's garden must not add one to a listing.
    suggested_amenities: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, server_default=text("'{}'::varchar[]")
    )

    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    flag_reason: Mapped[str | None] = mapped_column(String(200))
    #: Whether a human has acted on the suggestions. Until then nothing here
    #: affects the listing.
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    model: Mapped[str] = mapped_column(String(60), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("image_id", name="uq_image_annotations_image"),
        Index("ix_image_annotations_property", "property_id"),
        Index(
            "ix_image_annotations_flagged",
            "created_at",
            postgresql_where=text("flagged AND reviewed_at IS NULL"),
        ),
    )


class GeneratedItineraryModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A cached itinerary.

    Keyed by *what was asked*, not by who asked it. Two guests requesting four
    days in Goa for a couple get one generation and two fast responses. The
    consequence — and the reason nothing personal may enter the cache key — is
    that the request must contain nothing about the person, only about the
    trip.
    """

    __tablename__ = "generated_itineraries"

    #: SHA-256 over the normalised request. The cache key.
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    days: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    #: The full plan, as returned to clients.
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    #: Properties the plan actually references, after grounding. Lets a listing
    #: being unpublished invalidate the itineraries that point at it.
    referenced_property_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), nullable=False, server_default=text("'{}'::uuid[]")
    )
    #: The model's own admission that it was unsure. Rendered as a caveat
    #: rather than hidden — a plan presented with false confidence is worse
    #: than one that says it is a starting point.
    low_confidence: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    model: Mapped[str] = mapped_column(String(60), nullable=False)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("request_hash", name="uq_generated_itineraries_hash"),
        Index("ix_generated_itineraries_expiry", "expires_at"),
        Index("ix_generated_itineraries_refs", "referenced_property_ids", postgresql_using="gin"),
    )


class AssistantMessageModel(Base, UUIDPrimaryKeyMixin):
    """One turn of a chat conversation.

    Retained for a short window and then purged, because it is guest-authored
    free text: whatever the interface asks for, some fraction of people type a
    phone number, an address, or a booking reference into a chat box.

    ``created_at`` only, no ``updated_at``: a message is not edited. Correcting
    the record of what someone said is not a feature.
    """

    __tablename__ = "assistant_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    #: Nullable: anonymous visitors can use the assistant. Their conversation
    #: id is the only thread, and it dies with their session.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    #: Properties the assistant pointed at on this turn, after grounding.
    suggested_property_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), nullable=False, server_default=text("'{}'::uuid[]")
    )
    needs_human: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_assistant_messages_thread", "conversation_id", "created_at"),
        # Retention sweep. Partial on nothing — the whole table is swept — but
        # the index makes the delete a range scan rather than a table scan.
        Index("ix_assistant_messages_created", "created_at"),
    )


class AIUsageModel(Base, UUIDPrimaryKeyMixin):
    """What was spent, and by whom.

    Written on every model call that a user triggered. Redis holds the counters
    the budget check reads — this is the durable record, for answering "why was
    the bill that size" and for spotting one account driving all of it.

    Kept even when the call failed. A failing call still costs input tokens,
    and a burst of failures is exactly the pattern worth being able to see.
    """

    __tablename__ = "ai_usage"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    feature: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_ai_usage_feature_time", "feature", "created_at"),
        Index("ix_ai_usage_user_time", "user_id", "created_at"),
    )


__all__ = [
    "AIUsageModel",
    "AssistantMessageModel",
    "GeneratedItineraryModel",
    "ImageAnnotationModel",
    "PropertySentimentModel",
    "ReviewInsightModel",
]

# Kept unused-import-free while remaining explicit about the SQLAlchemy types
# this module relies on for column definitions.
_ = (Float,)
