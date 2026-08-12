"""payment: razorpay payments, refunds, append-only ledger, webhook dedupe

Revision ID: 0005_payment
Revises: 0004_booking
Created: 2026-08-06 20:00:00+00:00

Reviewer notes:

* **No card data anywhere.** `instrument` holds a last-4 or a UPI VPA and
  nothing else. A PAN — even encrypted — pulls the whole platform into PCI-DSS
  scope for cardholder data, and the only winning move is never to receive one.
  Razorpay's hosted checkout is what keeps that true.

* **`uq_payments_order_id` is the anti-double-charge constraint.** One order
  maps to exactly one payment row. Without it, "which payment does this webhook
  belong to?" becomes ambiguous at the worst possible moment, and a retry that
  reused an order could confirm a booking twice.

* **`uq_payment_refunds_idempotency` is the anti-double-refund constraint.**
  `(payment_id, idempotency_key)`, where the key is derived from the booking
  id. A retried Celery task and an impatient support agent clicking twice both
  collide here rather than sending two refunds. The same key also goes to
  Razorpay as a header, which covers the case where our row was never written.

* **`payment_ledger` is append-only and has a sign CHECK.** Charges are
  positive, everything else is negative, so `SUM(signed_minor)` over the table
  *is* the answer with no CASE expression a future reader could get wrong.
  Nothing in the code ever updates or deletes a row here — when the settlement
  report disagrees with our database, this is what makes the difference
  explainable instead of a mystery.

* **`payment_webhook_events.event_id` is the primary key.** Claiming a delivery
  is therefore `INSERT … ON CONFLICT DO NOTHING`: atomic, no transaction dance,
  which matters because two workers can receive the same Razorpay redelivery
  simultaneously and a SELECT-then-INSERT would let both proceed.

* **`payments.booking_id` is RESTRICT.** A payment record outlives everything
  around it — tax law, chargeback windows and dispute evidence all need it
  years later.

* Money columns are `BIGINT`, for the same reason as in 0004: a long luxury
  stay in paise exceeds a 32-bit int, and the failure mode is a silently wrong
  amount.

Additive only.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_payment"
down_revision: str | None = "0004_booking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── payments ──────────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_reference", sa.String(length=16), nullable=False),
        sa.Column("guest_id", postgresql.UUID(as_uuid=True), nullable=False),
        # ── gateway identity ──────────────────────────────────────────────
        sa.Column(
            "gateway", sa.String(length=20), server_default=sa.text("'razorpay'"), nullable=False
        ),
        sa.Column("gateway_order_id", sa.String(length=64), nullable=False),
        sa.Column("gateway_payment_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "method", sa.String(length=20), server_default=sa.text("'unknown'"), nullable=False
        ),
        # Last-4 or VPA. Never a PAN — see the module note above.
        sa.Column("instrument", sa.String(length=64), nullable=True),
        # ── money ─────────────────────────────────────────────────────────
        sa.Column("expected_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        # Razorpay's cut and the tax on it: not what the guest paid, but part of
        # what the platform receives. A reconciliation that ignores them never
        # balances against the settlement report.
        sa.Column("gateway_fee_minor", sa.BigInteger(), nullable=True),
        sa.Column("gateway_tax_minor", sa.BigInteger(), nullable=True),
        # ── lifecycle ─────────────────────────────────────────────────────
        sa.Column("attempt_number", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=60), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "notes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_payments_booking_id_bookings"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("gateway_order_id", name="uq_payments_order_id"),
        sa.UniqueConstraint("gateway_payment_id", name="uq_payments_gateway_payment_id"),
        sa.CheckConstraint(
            "status IN ('created','pending','authorized','captured','failed',"
            "'refunded','partially_refunded','disputed')",
            name=op.f("ck_payments_status_valid"),
        ),
        sa.CheckConstraint("expected_amount_minor > 0", name=op.f("ck_payments_amount_positive")),
        # Captured means money moved, which means there is a gateway payment id.
        sa.CheckConstraint(
            "captured_at IS NULL OR gateway_payment_id IS NOT NULL",
            name=op.f("ck_payments_captured_needs_gateway_id"),
        ),
    )
    op.create_index("ix_payments_booking", "payments", ["booking_id", "attempt_number"])
    op.create_index("ix_payments_guest", "payments", ["guest_id", sa.text("created_at DESC")])
    # The reconciliation job. Partial, because unsettled payments are a tiny
    # fraction of the table and this index should stay small enough to be hot.
    op.create_index(
        "ix_payments_unsettled",
        "payments",
        ["created_at"],
        postgresql_where=sa.text("status IN ('created','pending','authorized')"),
    )
    # The capture job.
    op.create_index(
        "ix_payments_authorized",
        "payments",
        ["authorized_at"],
        postgresql_where=sa.text("status = 'authorized'"),
    )
    op.execute(
        "CREATE TRIGGER trg_payments_updated_at BEFORE UPDATE ON payments "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # ── refunds ───────────────────────────────────────────────────────────
    op.create_table(
        "payment_refunds",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column(
            "speed", sa.String(length=10), server_default=sa.text("'normal'"), nullable=False
        ),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("gateway_refund_id", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_refunds")),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_refunds_payment_id_payments"),
            ondelete="CASCADE",
        ),
        # THE double-refund guard.
        sa.UniqueConstraint("payment_id", "idempotency_key", name="uq_payment_refunds_idempotency"),
        sa.UniqueConstraint("gateway_refund_id", name="uq_payment_refunds_gateway_id"),
        sa.CheckConstraint(
            "status IN ('pending','processed','failed')",
            name=op.f("ck_payment_refunds_status_valid"),
        ),
        sa.CheckConstraint("amount_minor > 0", name=op.f("ck_payment_refunds_amount_positive")),
    )
    op.create_index(
        "ix_payment_refunds_pending",
        "payment_refunds",
        ["requested_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.execute(
        "CREATE TRIGGER trg_payment_refunds_updated_at BEFORE UPDATE ON payment_refunds "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # ── ledger ────────────────────────────────────────────────────────────
    # Append-only. Nothing in the codebase updates or deletes a row here, and
    # that immutability is the entire value of the table.
    op.create_table(
        "payment_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("signed_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("gateway_reference", sa.String(length=64), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_ledger")),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_ledger_payment_id_payments"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('charge','refund','chargeback','gateway_fee','gateway_tax','adjustment')",
            name=op.f("ck_payment_ledger_kind_valid"),
        ),
        sa.CheckConstraint("amount_minor >= 0", name=op.f("ck_payment_ledger_amount_non_negative")),
        # The sign must agree with the kind, or a SUM over this table is
        # silently wrong in a way nobody notices until month end.
        sa.CheckConstraint(
            "(kind = 'charge' AND signed_minor >= 0) OR (kind <> 'charge' AND signed_minor <= 0)",
            name=op.f("ck_payment_ledger_sign_matches_kind"),
        ),
    )
    op.create_index("ix_payment_ledger_payment", "payment_ledger", ["payment_id", "occurred_at"])
    # The finance report: everything that moved in a period.
    op.create_index("ix_payment_ledger_period", "payment_ledger", ["occurred_at", "kind"])

    # ── webhook dedupe ────────────────────────────────────────────────────
    op.create_table(
        "payment_webhook_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        # The event id *is* the primary key — that is what makes claiming a
        # delivery atomic.
        sa.PrimaryKeyConstraint("event_id", name=op.f("pk_payment_webhook_events")),
    )
    # The replay queue: deliveries claimed but never completed.
    op.create_index(
        "ix_webhook_events_unprocessed",
        "payment_webhook_events",
        ["received_at"],
        postgresql_where=sa.text("processed_at IS NULL"),
    )
    op.create_index(
        "ix_webhook_events_type", "payment_webhook_events", ["event_type", "received_at"]
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_payment_refunds_updated_at ON payment_refunds")
    op.execute("DROP TRIGGER IF EXISTS trg_payments_updated_at ON payments")
    op.drop_table("payment_webhook_events")
    op.drop_table("payment_ledger")
    op.drop_table("payment_refunds")
    op.drop_table("payments")
