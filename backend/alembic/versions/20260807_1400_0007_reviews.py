"""reviews: verified-stay reviews, host replies, rating aggregates

Revision ID: 0007_review
Revises: 0006_admin
Created: 2026-08-07 14:00:00+00:00

Reviewer notes:

* **`uq_reviews_booking` is the integrity model.** One booking, one review. A
  review is written from a completed booking, not from a property id — the
  booking is the evidence that the author stayed there. Without the constraint,
  a guest with a grievance can post the same complaint ten times, and a retried
  request can double-count a rating that has already moved the average.

* **`booking_id` is RESTRICT; `author_id` is SET NULL.** The booking is the
  evidence and must outlive everything; a deleted account anonymises its reviews
  rather than silently rewriting a property's history by taking them with it.

* **`review_rating_summaries` stores a running *sum*, not an average.** Adding a
  review is `rating_total + rating`, which is exact; an average recomputed from
  an average drifts. The per-star counts live here too, because the
  distribution is what makes a rating readable and it does not belong on the
  listing row.

* **Flagged reviews stay visible.** Only `removed` disappears from the public
  list and stops counting. A host who could suppress criticism by objecting to
  it would make every rating on the platform meaningless, so the index that
  serves the public list filters on `moderation <> 'removed'` rather than on
  `= 'published'`.

* **`removal_needs_reason` is a CHECK.** Taking a review down is a decision
  someone has to be able to explain months later.

Additive only.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_review"
down_revision: str | None = "0006_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Denormalised so a vendor's review queue is one index scan.
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("author_name", sa.String(length=120), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "categories",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("stayed_on", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "moderation",
            sa.String(length=12),
            server_default=sa.text("'published'"),
            nullable=False,
        ),
        sa.Column("moderation_note", sa.Text(), nullable=True),
        sa.Column("host_reply", sa.Text(), nullable=True),
        sa.Column("host_replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_reviews_booking_id_bookings"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_reviews_property_id_properties"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name=op.f("fk_reviews_author_id_users"),
            ondelete="SET NULL",
        ),
        # One booking, one review. The whole integrity model.
        sa.UniqueConstraint("booking_id", name="uq_reviews_booking"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name=op.f("ck_reviews_rating_range")),
        sa.CheckConstraint(
            "moderation IN ('published','flagged','removed')",
            name=op.f("ck_reviews_moderation_valid"),
        ),
        sa.CheckConstraint(
            "moderation <> 'removed' OR moderation_note IS NOT NULL",
            name=op.f("ck_reviews_removal_needs_reason"),
        ),
        sa.CheckConstraint(
            "host_reply IS NULL OR host_replied_at IS NOT NULL",
            name=op.f("ck_reviews_reply_needs_time"),
        ),
    )
    # The public list. Filters on `<> 'removed'` so flagged reviews stay visible.
    op.create_index(
        "ix_reviews_property",
        "reviews",
        ["property_id", sa.text("published_at DESC")],
        postgresql_where=sa.text("moderation <> 'removed'"),
    )
    op.create_index("ix_reviews_vendor", "reviews", ["vendor_id", sa.text("published_at DESC")])
    # What a vendor actually opens the portal for.
    op.create_index(
        "ix_reviews_awaiting_reply",
        "reviews",
        ["vendor_id", "published_at"],
        postgresql_where=sa.text("host_reply IS NULL AND moderation <> 'removed'"),
    )
    op.create_index(
        "ix_reviews_flagged",
        "reviews",
        ["created_at"],
        postgresql_where=sa.text("moderation = 'flagged'"),
    )
    op.create_index(
        "ix_reviews_author",
        "reviews",
        ["author_id"],
        postgresql_where=sa.text("author_id IS NOT NULL"),
    )
    op.execute(
        "CREATE TRIGGER trg_reviews_updated_at BEFORE UPDATE ON reviews "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    op.create_table(
        "review_rating_summaries",
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        # A running sum, not an average — see the module note.
        sa.Column("rating_total", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("count_1", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("count_2", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("count_3", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("count_4", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("count_5", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "category_totals",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "category_counts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("property_id", name=op.f("pk_review_rating_summaries")),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_rating_summaries_property"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "review_count >= 0", name=op.f("ck_rating_summaries_count_non_negative")
        ),
        sa.CheckConstraint(
            "rating_total >= 0", name=op.f("ck_rating_summaries_total_non_negative")
        ),
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_reviews_updated_at ON reviews")
    op.drop_table("review_rating_summaries")
    op.drop_table("reviews")
