"""Saved properties.

One table. What it stores is what the guest created — which property, when,
their note — and nothing about how the listing looked at the time. Price and
rating are read live on every request, because a wishlist quoting last month's
price is a wishlist that misleads someone into clicking.

`name_snapshot` is the single exception and is a tombstone, not a cache: it is
rendered only when the listing is gone, so a guest sees what they lost instead
of a list that quietly got shorter.

Revision ID: 0010_wishlist
Revises: 0009_ai
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_wishlist"
down_revision = "0009_ai"
branch_labels = None
depends_on = None

_UUID = postgresql.UUID(as_uuid=True)
_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "wishlist_items",
        sa.Column("id", _UUID, primary_key=True),
        sa.Column("user_id", _UUID, nullable=False),
        sa.Column("property_id", _UUID, nullable=False),
        sa.Column("note", sa.String(280)),
        sa.Column("name_snapshot", sa.String(200), nullable=False),
        sa.Column("created_at", _TS, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", _TS, nullable=False, server_default=sa.func.now()),
        # CASCADE: a closed account's saved list is personal data with no
        # retention justification and no reader.
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_wishlist_user"
        ),
        # CASCADE on a *hard* delete only. Unpublishing leaves the row alone —
        # that is precisely what the tombstone column exists for.
        sa.ForeignKeyConstraint(
            ["property_id"], ["properties.id"], ondelete="CASCADE", name="fk_wishlist_property"
        ),
        # Saving twice is one save. Enforced here rather than by a prior read,
        # because a heart icon is exactly the control people double tap and
        # both taps race through any check-then-act.
        sa.UniqueConstraint("user_id", "property_id", name="uq_wishlist_user_property"),
        sa.CheckConstraint("length(trim(name_snapshot)) > 0", name="ck_wishlist_name_snapshot"),
    )
    # The list query, in its exact shape: one user's rows, newest first.
    op.create_index("ix_wishlist_user_saved", "wishlist_items", ["user_id", "created_at"])
    # "How many people saved this?" for the property module, and the reverse
    # lookup a delisting notification would need.
    op.create_index("ix_wishlist_property", "wishlist_items", ["property_id"])


def downgrade() -> None:
    op.drop_table("wishlist_items")
