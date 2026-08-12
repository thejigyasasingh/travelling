"""The saved-properties table.

Small, and the small decisions are the whole design.

**What is stored is what the guest created**: which property, when, and their
own note. Nothing about how the listing looked at the time — no price, no
rating, no image. Those are read live on every request, because a wishlist that
shows the price from the month it was saved is a wishlist that misleads someone
into clicking, and a stale price on a booking site is the one kind of stale
that costs money.

The single exception is `name_snapshot`, and it is a tombstone rather than a
cache: it is rendered only when the property is gone, so a guest sees "The
Anjuna House — no longer available" instead of a list that quietly got shorter.
Never preferred over the live name.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin

#: Long enough for "for Ma's birthday — check the step-free access", short
#: enough that nobody writes their itinerary in it.
MAX_NOTE = 280


class WishlistItemModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "wishlist_items"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        # CASCADE: a deleted account's saved list is not a record anyone needs,
        # and it is personal data with no retention justification.
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        # CASCADE on a *hard* delete only. A property being unpublished leaves
        # the row alone — that is exactly the case `name_snapshot` exists for.
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(String(MAX_NOTE))
    name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        # Saving twice is one save. Enforced here rather than by a prior read,
        # because a double tap on a slow connection passes any check-then-act —
        # and a heart icon is precisely the control people double tap.
        UniqueConstraint("user_id", "property_id", name="uq_wishlist_user_property"),
        # The list query: one user's items, newest first.
        Index("ix_wishlist_user_saved", "user_id", "created_at"),
    )
