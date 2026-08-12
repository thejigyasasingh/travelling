"""admin: vendors, coupons, support tickets, notification log

Revision ID: 0006_admin
Revises: 0005_payment
Created: 2026-08-07 10:00:00+00:00

Reviewer notes:

* **`vendors` holds no full bank account number and no document images.** Only
  a last-4, an IFSC and the tax identifiers the platform is legally required to
  keep. Account numbers go to the payout provider directly; KYC documents live
  in object storage behind signed URLs. A table holding either becomes the most
  attractive thing in the database.

* **`approved_needs_evidence` is a CHECK, not a convention.** An approved
  vendor is one a human signed off with a PAN on file — that is what TDS is
  filed against, and a payout to a vendor without one is a payable finance
  cannot legally settle.

* **`coupons.percent_needs_cap` is the expensive one.** An uncapped 20% on a
  ₹4,00,000 villa week is ₹80,000. The constraint refuses the coupon at
  creation rather than letting it be discovered in a revenue report.

* **`coupon_redemptions` is what makes limits real.** `redeemed_count` on the
  coupon is maintained by a conditional UPDATE, and
  `redemptions_within_limit` guarantees it can never exceed the limit whatever
  the application does. `uq_redemption_booking` stops a retried request
  discounting the same booking twice.

* **Support messages are one table with an `is_internal` flag**, not two
  tables. Two tables guarantee that one day a query forgets the filter and an
  internal note is rendered to the guest; one table makes the dangerous case
  the one you have to opt into.

* **`notifications` stores no rendered body** — a template name, redacted
  context and a short preview. A confirmation body contains the guest's address
  and booking reference, and a table of them grows forever for no operational
  benefit.

Additive only. Nothing here touches an existing table.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_admin"
down_revision: str | None = "0005_payment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── vendors ───────────────────────────────────────────────────────────
    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("contact_email", sa.String(length=320), nullable=False),
        sa.Column("contact_phone", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("gstin", sa.String(length=15), nullable=True),
        sa.Column("pan", sa.String(length=10), nullable=True),
        # Last four digits only — see the module note.
        sa.Column("bank_account_last4", sa.String(length=4), nullable=True),
        sa.Column("bank_ifsc", sa.String(length=11), nullable=True),
        sa.Column("commission_bps", sa.Integer(), server_default=sa.text("1500"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("suspension_reason", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendors")),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_vendors_owner_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("owner_user_id", name="uq_vendors_owner"),
        sa.UniqueConstraint("gstin", name="uq_vendors_gstin"),
        sa.UniqueConstraint("pan", name="uq_vendors_pan"),
        sa.CheckConstraint(
            "status IN ('pending','under_review','approved','rejected','suspended')",
            name=op.f("ck_vendors_status_valid"),
        ),
        sa.CheckConstraint(
            "commission_bps BETWEEN 0 AND 3000", name=op.f("ck_vendors_commission_within_range")
        ),
        sa.CheckConstraint(
            "status <> 'approved' OR (approved_at IS NOT NULL AND pan IS NOT NULL)",
            name=op.f("ck_vendors_approved_needs_evidence"),
        ),
    )
    op.create_index(
        "ix_vendors_review_queue",
        "vendors",
        ["created_at"],
        postgresql_where=sa.text("status IN ('pending','under_review')"),
    )
    op.create_index("ix_vendors_status", "vendors", ["status", "created_at"])
    op.execute(
        "CREATE TRIGGER trg_vendors_updated_at BEFORE UPDATE ON vendors "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # ── coupons ───────────────────────────────────────────────────────────
    op.create_table(
        "coupons",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("discount_type", sa.String(length=10), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column(
            "status", sa.String(length=10), server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "min_booking_minor", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("max_discount_minor", sa.BigInteger(), nullable=True),
        sa.Column("total_limit", sa.Integer(), nullable=True),
        sa.Column("per_user_limit", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "first_booking_only", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "property_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("redeemed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coupons")),
        sa.UniqueConstraint("code", name="uq_coupons_code"),
        sa.CheckConstraint(
            "discount_type IN ('percent','flat')", name=op.f("ck_coupons_type_valid")
        ),
        sa.CheckConstraint(
            "status IN ('active','inactive','expired')", name=op.f("ck_coupons_status_valid")
        ),
        sa.CheckConstraint("value > 0", name=op.f("ck_coupons_value_positive")),
        sa.CheckConstraint("ends_at > starts_at", name=op.f("ck_coupons_window_ordered")),
        sa.CheckConstraint("per_user_limit >= 1", name=op.f("ck_coupons_per_user_limit_positive")),
        sa.CheckConstraint(
            "discount_type <> 'percent' OR value <= 10000",
            name=op.f("ck_coupons_percent_within_range"),
        ),
        # The expensive one. See the module note.
        sa.CheckConstraint(
            "discount_type <> 'percent' OR max_discount_minor IS NOT NULL",
            name=op.f("ck_coupons_percent_needs_cap"),
        ),
        sa.CheckConstraint(
            "total_limit IS NULL OR redeemed_count <= total_limit",
            name=op.f("ck_coupons_redemptions_within_limit"),
        ),
    )
    op.create_index(
        "ix_coupons_live",
        "coupons",
        ["ends_at"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.execute(
        "CREATE TRIGGER trg_coupons_updated_at BEFORE UPDATE ON coupons "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    op.create_table(
        "coupon_redemptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("coupon_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "redeemed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coupon_redemptions")),
        sa.ForeignKeyConstraint(
            ["coupon_id"],
            ["coupons.id"],
            name=op.f("fk_coupon_redemptions_coupon_id_coupons"),
            ondelete="RESTRICT",
        ),
        # A retried booking request must not discount twice.
        sa.UniqueConstraint("coupon_id", "booking_id", name="uq_redemption_booking"),
        sa.CheckConstraint(
            "discount_minor >= 0", name=op.f("ck_coupon_redemptions_discount_non_negative")
        ),
    )
    op.create_index("ix_redemptions_user", "coupon_redemptions", ["coupon_id", "user_id"])
    op.create_index("ix_redemptions_reporting", "coupon_redemptions", ["redeemed_at", "coupon_id"])

    # ── support ───────────────────────────────────────────────────────────
    op.create_table(
        "support_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference", sa.String(length=16), nullable=False),
        sa.Column("requester_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requester_name", sa.String(length=120), nullable=False),
        sa.Column("requester_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'open'"), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("first_responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_tickets")),
        # SET NULL, not CASCADE: a deleted account must not erase the support
        # history that explains a refund someone may still query.
        sa.ForeignKeyConstraint(
            ["requester_id"],
            ["users.id"],
            name=op.f("fk_support_tickets_requester_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
            name=op.f("fk_support_tickets_assigned_to_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_support_tickets_booking_id_bookings"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("reference", name="uq_tickets_reference"),
        sa.CheckConstraint(
            "status IN ('open','in_progress','waiting_on_guest','resolved','closed')",
            name=op.f("ck_support_tickets_status_valid"),
        ),
        sa.CheckConstraint(
            "priority IN ('urgent','high','normal','low')",
            name=op.f("ck_support_tickets_priority_valid"),
        ),
        sa.CheckConstraint(
            "status <> 'resolved' OR resolution IS NOT NULL",
            name=op.f("ck_support_tickets_resolved_needs_resolution"),
        ),
    )
    op.create_index(
        "ix_tickets_queue",
        "support_tickets",
        ["priority", "opened_at"],
        postgresql_where=sa.text("status IN ('open','in_progress','waiting_on_guest')"),
    )
    op.create_index(
        "ix_tickets_assigned",
        "support_tickets",
        ["assigned_to", "status"],
        postgresql_where=sa.text("assigned_to IS NOT NULL"),
    )
    op.create_index("ix_tickets_requester", "support_tickets", ["requester_email", "opened_at"])
    op.create_index(
        "ix_tickets_booking",
        "support_tickets",
        ["booking_id"],
        postgresql_where=sa.text("booking_id IS NOT NULL"),
    )
    op.execute(
        "CREATE TRIGGER trg_support_tickets_updated_at BEFORE UPDATE ON support_tickets "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    op.create_table(
        "support_ticket_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("author_name", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        # The flag that keeps agents' notes away from the guest.
        sa.Column("is_internal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_ticket_messages")),
        sa.ForeignKeyConstraint(
            ["ticket_id"],
            ["support_tickets.id"],
            name=op.f("fk_ticket_messages_ticket_id"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_ticket_messages_thread", "support_ticket_messages", ["ticket_id", "sent_at"]
    )

    # ── notifications ─────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(length=10), nullable=False),
        sa.Column("template", sa.String(length=60), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=True),
        # A preview only. Never the rendered body.
        sa.Column("preview", sa.String(length=200), nullable=True),
        sa.Column(
            "context",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=12), server_default=sa.text("'queued'"), nullable=False
        ),
        sa.Column("provider_message_id", sa.String(length=120), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("dedupe_key", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        # What makes a retried task idempotent.
        sa.UniqueConstraint("dedupe_key", name="uq_notifications_dedupe"),
        sa.CheckConstraint(
            "channel IN ('email','sms','push','whatsapp')",
            name=op.f("ck_notifications_channel_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('queued','sent','failed','suppressed')",
            name=op.f("ck_notifications_status_valid"),
        ),
    )
    op.create_index(
        "ix_notifications_recipient", "notifications", ["recipient", sa.text("created_at DESC")]
    )
    op.create_index(
        "ix_notifications_failed",
        "notifications",
        ["created_at"],
        postgresql_where=sa.text("status = 'failed'"),
    )
    op.create_index(
        "ix_notifications_template", "notifications", ["template", sa.text("created_at DESC")]
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_support_tickets_updated_at ON support_tickets")
    op.execute("DROP TRIGGER IF EXISTS trg_coupons_updated_at ON coupons")
    op.execute("DROP TRIGGER IF EXISTS trg_vendors_updated_at ON vendors")
    op.drop_table("notifications")
    op.drop_table("support_ticket_messages")
    op.drop_table("support_tickets")
    op.drop_table("coupon_redemptions")
    op.drop_table("coupons")
    op.drop_table("vendors")
