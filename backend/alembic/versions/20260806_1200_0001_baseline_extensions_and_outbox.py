"""baseline: extensions, updated_at trigger, outbox

Revision ID: 0001_baseline
Revises:
Created: 2026-08-06 12:00:00+00:00

The foundation every later migration assumes:

1. **Extensions.** ``btree_gist`` is what makes the no-overbooking exclusion
   constraint possible (it lets a GiST index mix a ``daterange`` with a plain
   equality column). ``pg_trgm`` backs fuzzy city/property search. ``citext``
   gives case-insensitive emails without a functional index on every lookup.
2. **The ``set_updated_at`` trigger function.** ``updated_at`` is maintained by
   the database, not by SQLAlchemy's ``onupdate`` — see the note in
   ``mixins.py``. Bulk updates, data migrations and manual DBA fixes all bypass
   the ORM, and CDC and cache invalidation key off this column.
3. **The outbox table**, which every module's events land in.

A dedicated application role is *not* created here — role and grant management
belongs to Terraform, so that the migration user's own permissions are not
something a migration can change.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UPDATED_AT_FN = """
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    -- Only touch the row when something actually changed. An UPDATE that sets
    -- a column to its existing value should not bump updated_at, or every
    -- idempotent write invalidates caches and re-triggers CDC downstream.
    IF row_to_json(NEW)::text IS DISTINCT FROM row_to_json(OLD)::text THEN
        NEW.updated_at = now();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    # ── extensions ────────────────────────────────────────────────────────
    # IF NOT EXISTS: on managed Postgres (RDS/Aurora) some of these may already
    # be installed by the platform.
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')  # gen_random_uuid, digest
    op.execute('CREATE EXTENSION IF NOT EXISTS "btree_gist"')  # exclusion constraints
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')  # trigram search
    op.execute('CREATE EXTENSION IF NOT EXISTS "citext"')  # case-insensitive email
    op.execute('CREATE EXTENSION IF NOT EXISTS "unaccent"')  # "Bengaluru" ~ "Bengalūru"

    # ── shared trigger function ───────────────────────────────────────────
    op.execute(UPDATED_AT_FN)

    # ── outbox ────────────────────────────────────────────────────────────
    op.create_table(
        "outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(length=40), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("event_version", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox")),
    )

    # Partial index: the relay polls this every second forever. Processed rows
    # accumulate into the millions before archival, and a full index over them
    # would grow without bound while only the pending tail is ever queried.
    # Restricted to the exact predicate in outbox_relay.relay_batch.
    op.create_index(
        "ix_outbox_pending",
        "outbox",
        ["created_at"],
        postgresql_where=sa.text("processed_at IS NULL AND attempts < 10"),
    )
    # Supports "replay everything that happened to booking X" during an
    # incident investigation.
    op.create_index("ix_outbox_aggregate", "outbox", ["aggregate_type", "aggregate_id"])
    # Drives the archival job that moves processed rows to cold storage.
    op.create_index(
        "ix_outbox_processed",
        "outbox",
        ["processed_at"],
        postgresql_where=sa.text("processed_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_processed", table_name="outbox")
    op.drop_index("ix_outbox_aggregate", table_name="outbox")
    op.drop_index("ix_outbox_pending", table_name="outbox")
    op.drop_table("outbox")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    # Extensions are intentionally NOT dropped. They may be in use by another
    # schema in the same database, and dropping pg_trgm would silently
    # invalidate indexes that depend on it.
