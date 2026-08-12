"""booking: reservations, refunds, gapless invoice sequences

Revision ID: 0004_booking
Revises: 0003_property
Created: 2026-08-06 18:00:00+00:00

Reviewer notes:

* **``total_is_sum_of_parts`` is a CHECK, not a comment.** The aggregate
  enforces it too, but only for writes that go through the aggregate — a data
  migration or a support script does not. For money, "everything else" is
  where the expensive mistakes happen.
* **``bookings.reference`` and ``invoice_number`` are unique.** The reference
  is generated randomly, so a collision is astronomically unlikely but not
  impossible; the constraint turns it into a retry rather than two guests
  sharing a reference.
* **``booking_refunds`` is one row per booking**, enforced. Refunding twice is
  real money leaving twice, and a retried webhook racing an impatient support
  agent is exactly how it happens.
* **``invoice_sequences`` replaces a Postgres SEQUENCE** deliberately.
  Sequences are non-transactional: they do not roll back, so every failed
  transaction burns a number. Indian GST requires consecutive invoice
  numbering, and a gap must be explained to an auditor.
* **Foreign keys to properties and room_types are RESTRICT, not CASCADE.**
  Deleting a property out from under a booking would destroy the record a
  refund, an invoice and a tax filing depend on.
* Money columns are ``BIGINT``: a 90-night luxury villa booking in paise
  exceeds a 32-bit int, and the failure mode is a silently wrong amount.

Additive only.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_booking"
down_revision: str | None = "0003_property"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        # ── parties ───────────────────────────────────────────────────────
        sa.Column("guest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("room_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        # ── snapshots, frozen at booking time ─────────────────────────────
        sa.Column("property_name", sa.String(length=200), nullable=False),
        sa.Column("room_type_name", sa.String(length=120), nullable=False),
        sa.Column("cancellation_policy", sa.String(length=20), nullable=False),
        # ── stay ──────────────────────────────────────────────────────────
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=False),
        sa.Column(
            "check_in_time",
            sa.String(length=5),
            server_default=sa.text("'14:00'"),
            nullable=False,
        ),
        sa.Column(
            "check_out_time",
            sa.String(length=5),
            server_default=sa.text("'11:00'"),
            nullable=False,
        ),
        sa.Column(
            "timezone",
            sa.String(length=50),
            server_default=sa.text("'Asia/Kolkata'"),
            nullable=False,
        ),
        sa.Column(
            "stay_range",
            postgresql.DATERANGE(),
            server_default=sa.text("daterange(CURRENT_DATE, CURRENT_DATE + 1, '[)')"),
            nullable=False,
        ),
        # ── party ─────────────────────────────────────────────────────────
        sa.Column("adults", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("children", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("infants", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("rooms", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        # ── guest ─────────────────────────────────────────────────────────
        sa.Column("guest_name", sa.String(length=150), nullable=False),
        sa.Column("guest_email", sa.String(length=254), nullable=False),
        sa.Column("guest_phone", sa.String(length=20), nullable=False),
        sa.Column("special_requests", sa.Text()),
        # ── money ─────────────────────────────────────────────────────────
        sa.Column("accommodation_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "extra_guest_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "cleaning_fee_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("tax_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "platform_fee_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'INR'"), nullable=False),
        sa.Column(
            "nightly_rates",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        # ── lifecycle ─────────────────────────────────────────────────────
        sa.Column("hold_expires_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_by", sa.String(length=10)),
        sa.Column("cancellation_reason", sa.Text()),
        sa.Column("payment_id", sa.String(length=100)),
        sa.Column("invoice_number", sa.String(length=30)),
        sa.Column("invoice_issued_at", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(length=20), server_default=sa.text("'web'"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bookings")),
        sa.ForeignKeyConstraint(
            ["guest_id"],
            ["users.id"],
            name=op.f("fk_bookings_guest_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name=op.f("fk_bookings_property_id_properties"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["room_type_id"],
            ["room_types.id"],
            name=op.f("fk_bookings_room_type_id_room_types"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("reference", name="uq_bookings_reference"),
        sa.UniqueConstraint("invoice_number", name="uq_bookings_invoice_number"),
        sa.CheckConstraint(
            "status IN ('pending_payment','pending_approval','confirmed','in_stay',"
            "'completed','cancelled','expired','rejected','no_show')",
            name=op.f("ck_bookings_status_valid"),
        ),
        sa.CheckConstraint("check_out > check_in", name=op.f("ck_bookings_dates_ordered")),
        sa.CheckConstraint("adults >= 1", name=op.f("ck_bookings_at_least_one_adult")),
        sa.CheckConstraint("rooms >= 1", name=op.f("ck_bookings_at_least_one_room")),
        # THE money invariant.
        sa.CheckConstraint(
            "total_minor = accommodation_minor + extra_guest_minor + cleaning_fee_minor "
            "+ tax_minor + platform_fee_minor",
            name=op.f("ck_bookings_total_is_sum_of_parts"),
        ),
        sa.CheckConstraint("total_minor >= 0", name=op.f("ck_bookings_total_non_negative")),
        sa.CheckConstraint(
            "confirmed_at IS NULL OR payment_id IS NOT NULL",
            name=op.f("ck_bookings_confirmed_needs_payment"),
        ),
    )

    op.execute("CREATE INDEX ix_bookings_guest ON bookings (guest_id, created_at DESC)")
    op.create_index("ix_bookings_vendor_dates", "bookings", ["vendor_id", "check_in", "status"])
    op.create_index("ix_bookings_property_dates", "bookings", ["property_id", "check_in"])
    op.create_index("ix_bookings_created_at", "bookings", ["created_at"])
    # Partial: holds are a tiny, short-lived fraction of the table, and the
    # expiry job runs every minute forever.
    op.create_index(
        "ix_bookings_expiring",
        "bookings",
        ["hold_expires_at"],
        postgresql_where=sa.text("status IN ('pending_payment','pending_approval')"),
    )
    op.create_index(
        "ix_bookings_active_stays",
        "bookings",
        ["check_out", "check_in"],
        postgresql_where=sa.text("status IN ('confirmed','in_stay')"),
    )
    # Overlap questions over a room type in one GiST lookup.
    op.create_index(
        "ix_bookings_stay_range",
        "bookings",
        ["room_type_id", "stay_range"],
        postgresql_using="gist",
    )

    op.execute(
        "CREATE TRIGGER trg_bookings_updated_at BEFORE UPDATE ON bookings "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # ── refunds ───────────────────────────────────────────────────────────
    op.create_table(
        "booking_refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column(
            "breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("gateway_refund_id", sa.String(length=100)),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_refunds")),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_booking_refunds_booking_id_bookings"),
            ondelete="CASCADE",
        ),
        # One refund per booking. Refunding twice is real money leaving twice.
        sa.UniqueConstraint("booking_id", name="uq_booking_refunds_booking"),
        sa.CheckConstraint(
            "status IN ('pending','processing','completed','failed')",
            name=op.f("ck_booking_refunds_status_valid"),
        ),
        sa.CheckConstraint("amount_minor > 0", name=op.f("ck_booking_refunds_amount_positive")),
    )
    op.create_index(
        "ix_booking_refunds_pending",
        "booking_refunds",
        ["requested_at"],
        postgresql_where=sa.text("status IN ('pending','failed')"),
    )
    op.create_index("ix_booking_refunds_created_at", "booking_refunds", ["created_at"])

    # ── gapless invoice numbering ─────────────────────────────────────────
    op.create_table(
        "invoice_sequences",
        sa.Column("financial_year", sa.String(length=7), nullable=False),
        sa.Column("series", sa.String(length=10), nullable=False),
        sa.Column("last_number", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("financial_year", "series", name=op.f("pk_invoice_sequences")),
        sa.CheckConstraint("last_number >= 0", name=op.f("ck_invoice_sequences_non_negative")),
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_bookings_updated_at ON bookings")
    op.drop_table("invoice_sequences")
    op.drop_table("booking_refunds")
    op.drop_table("bookings")
