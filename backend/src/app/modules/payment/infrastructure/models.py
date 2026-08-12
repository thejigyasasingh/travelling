"""Payment persistence.

Two things carry the design weight: the money CHECK constraints, and the
append-only ledger.

**No card data is stored, ever.** Only Razorpay's opaque ids, the method, and a
last-4 or VPA for recognition. The platform is therefore out of PCI-DSS scope
for cardholder data — storing a PAN, even encrypted, changes the compliance
burden entirely and is never worth it.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin


class PaymentModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin):
    __tablename__ = "payments"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        # RESTRICT: a payment record outlives everything. Tax law, chargeback
        # windows and dispute evidence all need it years later.
        PGUUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    booking_reference: Mapped[str] = mapped_column(String(16), nullable=False)
    guest_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)

    gateway: Mapped[str] = mapped_column(String(20), server_default=text("'razorpay'"))
    gateway_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    method: Mapped[str] = mapped_column(String(20), server_default=text("'unknown'"))
    #: Card last-4 or UPI VPA. Enough for a guest to recognise the instrument;
    #: never a PAN, which we never receive.
    instrument: Mapped[str | None] = mapped_column(String(64))

    expected_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    #: Razorpay's cut and the tax on it. Not part of what the guest paid, but
    #: part of what the platform receives — a reconciliation that ignores them
    #: never balances against the settlement report.
    gateway_fee_minor: Mapped[int | None] = mapped_column(BigInteger)
    gateway_tax_minor: Mapped[int | None] = mapped_column(BigInteger)

    attempt_number: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("1")
    )
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(60))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    refunds: Mapped[list[PaymentRefundModel]] = relationship(
        back_populates="payment", cascade="all, delete-orphan", lazy="selectin"
    )
    ledger: Mapped[list[LedgerEntryModel]] = relationship(
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LedgerEntryModel.occurred_at",
    )

    __mapper_args__ = {"version_id_col": VersionMixin.version}  # noqa: RUF012

    __table_args__ = (
        # An order maps to exactly one payment. Two would make "which payment
        # does this webhook belong to?" ambiguous at the worst moment.
        UniqueConstraint("gateway_order_id", name="uq_payments_order_id"),
        UniqueConstraint("gateway_payment_id", name="uq_payments_gateway_payment_id"),
        CheckConstraint(
            "status IN ('created','pending','authorized','captured','failed',"
            "'refunded','partially_refunded','disputed')",
            name="status_valid",
        ),
        CheckConstraint("expected_amount_minor > 0", name="amount_positive"),
        # Captured means money moved, which means there is a gateway payment id.
        CheckConstraint(
            "captured_at IS NULL OR gateway_payment_id IS NOT NULL",
            name="captured_needs_gateway_id",
        ),
        Index("ix_payments_booking", "booking_id", "attempt_number"),
        Index("ix_payments_guest", "guest_id", text("created_at DESC")),
        # The reconciliation job: payments stuck in a non-terminal state whose
        # webhook never arrived. Partial, because they are a tiny fraction.
        Index(
            "ix_payments_unsettled",
            "created_at",
            postgresql_where=text("status IN ('created','pending','authorized')"),
        ),
        # The capture job.
        Index(
            "ix_payments_authorized",
            "authorized_at",
            postgresql_where=text("status = 'authorized'"),
        ),
    )


class PaymentRefundModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payment_refunds"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    booking_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    speed: Mapped[str] = mapped_column(String(10), server_default=text("'normal'"))
    #: Sent to Razorpay as a header. Unique per payment, which is what makes a
    #: retried task refund once rather than twice.
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    gateway_refund_id: Mapped[str | None] = mapped_column(String(64))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    payment: Mapped[PaymentModel] = relationship(back_populates="refunds", lazy="raise_on_sql")

    __table_args__ = (
        # THE double-refund guard. A retried webhook racing an impatient
        # support agent is exactly how it happens.
        UniqueConstraint("payment_id", "idempotency_key", name="uq_payment_refunds_idempotency"),
        UniqueConstraint("gateway_refund_id", name="uq_payment_refunds_gateway_id"),
        CheckConstraint("status IN ('pending','processed','failed')", name="status_valid"),
        CheckConstraint("amount_minor > 0", name="amount_positive"),
        Index(
            "ix_payment_refunds_pending",
            "requested_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )


class LedgerEntryModel(Base, UUIDPrimaryKeyMixin):
    """Append-only record of every money movement.

    Never updated, never deleted. A payment's true net is `sum(signed_minor)`,
    not a maintained column — and when the settlement report disagrees with our
    database, this is what makes the difference explainable rather than a
    mystery.
    """

    __tablename__ = "payment_ledger"

    payment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    booking_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    #: Positive for money in, negative for money out. Stored rather than
    #: derived so a `SUM()` over the table is the answer, with no CASE
    #: expression that a future reader could get wrong.
    signed_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    gateway_reference: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    payment: Mapped[PaymentModel] = relationship(back_populates="ledger", lazy="raise_on_sql")

    __table_args__ = (
        CheckConstraint(
            "kind IN ('charge','refund','chargeback','gateway_fee','gateway_tax','adjustment')",
            name="kind_valid",
        ),
        CheckConstraint("amount_minor >= 0", name="amount_non_negative"),
        # The sign must agree with the kind, or a SUM over the table is
        # silently wrong in a way nobody notices until month end.
        CheckConstraint(
            "(kind = 'charge' AND signed_minor >= 0) OR (kind <> 'charge' AND signed_minor <= 0)",
            name="sign_matches_kind",
        ),
        Index("ix_payment_ledger_payment", "payment_id", "occurred_at"),
        # The finance report: everything that moved in a period.
        Index("ix_payment_ledger_period", "occurred_at", "kind"),
    )


class WebhookEventModel(Base):
    """Deduplication for webhook deliveries.

    Razorpay redelivers on any non-2xx, and duplicates arrive even after a 200.
    The event id is the primary key, so claiming a delivery is an INSERT whose
    conflict means "already seen" — atomic, with no transaction dance, which
    matters because two workers can receive the same redelivery simultaneously.

    The raw payload is kept for a while: when a webhook is mishandled, being
    able to replay the exact delivery is the difference between fixing it and
    guessing.
    """

    __tablename__ = "payment_webhook_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # The replay queue: deliveries claimed but never completed.
        Index(
            "ix_webhook_events_unprocessed",
            "received_at",
            postgresql_where=text("processed_at IS NULL"),
        ),
        Index("ix_webhook_events_type", "event_type", "received_at"),
    )
