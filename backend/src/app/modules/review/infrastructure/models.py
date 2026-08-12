"""Review persistence.

`uq_reviews_booking` is the rule made structural: **one booking, one review**.
Without it, a guest with a grievance can post the same complaint ten times and
sink a rating, and a retried request can double-count a rating that has already
moved the average.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin


class ReviewModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin):
    __tablename__ = "reviews"

    #: The evidence. A review exists because a stay did.
    booking_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=False
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False
    )
    #: Denormalised so a vendor's review queue is one index scan rather than a
    #: join through properties on every page.
    vendor_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    author_id: Mapped[uuid.UUID] = mapped_column(
        # SET NULL, not CASCADE: a deleted account must not silently rewrite a
        # property's history by taking its reviews with it.
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_name: Mapped[str] = mapped_column(String(120), nullable=False)

    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    #: Per-category sub-scores. JSONB rather than six columns: the set changes
    #: with product decisions, and a guest may skip any of them.
    categories: Mapped[dict[str, int]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    stayed_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderation: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=text("'published'")
    )
    moderation_note: Mapped[str | None] = mapped_column(Text)

    host_reply: Mapped[str | None] = mapped_column(Text)
    host_replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __mapper_args__ = {"version_id_col": VersionMixin.version}  # noqa: RUF012

    __table_args__ = (
        # One booking, one review. See the module docstring.
        UniqueConstraint("booking_id", name="uq_reviews_booking"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
        CheckConstraint("moderation IN ('published','flagged','removed')", name="moderation_valid"),
        # Removing a review is a decision someone has to be able to explain.
        CheckConstraint(
            "moderation <> 'removed' OR moderation_note IS NOT NULL",
            name="removal_needs_reason",
        ),
        CheckConstraint(
            "host_reply IS NULL OR host_replied_at IS NOT NULL", name="reply_needs_time"
        ),
        # The public review list for one property, newest first.
        Index(
            "ix_reviews_property",
            "property_id",
            text("published_at DESC"),
            postgresql_where=text("moderation <> 'removed'"),
        ),
        # The vendor's queue: their reviews, unanswered ones first in the app.
        Index("ix_reviews_vendor", "vendor_id", text("published_at DESC")),
        # What a vendor actually opens the portal for.
        Index(
            "ix_reviews_awaiting_reply",
            "vendor_id",
            "published_at",
            postgresql_where=text("host_reply IS NULL AND moderation <> 'removed'"),
        ),
        # The moderation queue.
        Index(
            "ix_reviews_flagged",
            "created_at",
            postgresql_where=text("moderation = 'flagged'"),
        ),
        Index("ix_reviews_author", "author_id", postgresql_where=text("author_id IS NOT NULL")),
    )


class ReviewRatingSummary(Base):
    """A property's rating, maintained rather than computed on read.

    A property page renders the average on every view, and a search result
    renders fifty of them. Recomputing `avg(rating)` per property per request is
    a scan of every review the property has ever had, so the aggregate is kept
    here and updated when a review lands or is removed.

    Kept in its own table rather than only on `properties` because the
    distribution — how many 5s, how many 1s — is what makes a rating readable,
    and it does not belong on the listing row.
    """

    __tablename__ = "review_rating_summaries"

    property_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        primary_key=True,
    )
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    #: Sum rather than average: adding one review is `+rating`, and an average
    #: recomputed from an average drifts.
    rating_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    count_1: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    count_2: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    count_3: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    count_4: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    count_5: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    category_totals: Mapped[dict[str, int]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    category_counts: Mapped[dict[str, int]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("review_count >= 0", name="count_non_negative"),
        CheckConstraint("rating_total >= 0", name="total_non_negative"),
    )
