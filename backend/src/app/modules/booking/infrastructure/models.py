"""Booking persistence.

The money columns carry CHECK constraints that repeat rules the aggregate also
enforces. That duplication is deliberate: the aggregate guards the paths that
go through it, and the database guards everything else — a data migration, a
support script, a future service. For money, "everything else" is where the
expensive mistakes happen.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
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
from sqlalchemy.dialects.postgresql import DATERANGE, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin


class BookingModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin):
    __tablename__ = "bookings"

    reference: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    # ── parties ───────────────────────────────────────────────────────────
    guest_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        # RESTRICT, not CASCADE. A property is soft-deleted, never removed —
        # deleting one out from under a booking would destroy the record a
        # refund, an invoice and a tax filing all depend on.
        PGUUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    room_type_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("room_types.id", ondelete="RESTRICT"), nullable=False
    )

    # ── snapshots ─────────────────────────────────────────────────────────
    # Copied at booking time, not joined. A vendor renaming their property or
    # changing their cancellation policy must not alter what an existing guest
    # agreed to, and the invoice must still say what it said when issued.
    property_name: Mapped[str] = mapped_column(String(200), nullable=False)
    room_type_name: Mapped[str] = mapped_column(String(120), nullable=False)
    cancellation_policy: Mapped[str] = mapped_column(String(20), nullable=False)

    # ── stay ──────────────────────────────────────────────────────────────
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    check_in_time: Mapped[str] = mapped_column(String(5), server_default=text("'14:00'"))
    check_out_time: Mapped[str] = mapped_column(String(5), server_default=text("'11:00'"))
    timezone: Mapped[str] = mapped_column(String(50), server_default=text("'Asia/Kolkata'"))
    #: Generated half-open [check_in, check_out) range. Exists so overlap
    #: questions ("which bookings touch this week?") are a single GiST index
    #: lookup rather than two comparisons the planner handles poorly.
    stay_range: Mapped[Any] = mapped_column(
        DATERANGE,
        nullable=False,
        server_default=text("daterange(CURRENT_DATE, CURRENT_DATE + 1, '[)')"),
    )

    # ── party ─────────────────────────────────────────────────────────────
    adults: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    children: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    infants: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    rooms: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))

    # ── guest details ─────────────────────────────────────────────────────
    # On the booking, not read from the account: people book for other people,
    # and the account's name may change while the invoice must not.
    guest_name: Mapped[str] = mapped_column(String(150), nullable=False)
    guest_email: Mapped[str] = mapped_column(String(254), nullable=False)
    guest_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    special_requests: Mapped[str | None] = mapped_column(Text)

    # ── money ─────────────────────────────────────────────────────────────
    # BigInteger: a 90-night booking of a luxury villa in paise exceeds a
    # 32-bit int, and discovering that in production means a silently wrong
    # amount rather than an error.
    accommodation_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    extra_guest_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    cleaning_fee_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    tax_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    platform_fee_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    total_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default=text("'INR'"))

    #: Per-night breakdown as it was quoted. Kept so a guest disputing a charge
    #: can be shown exactly which night cost what, months later, after the
    #: vendor has changed their rates twice.
    nightly_rates: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    # ── lifecycle ─────────────────────────────────────────────────────────
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[str | None] = mapped_column(String(10))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)

    payment_id: Mapped[str | None] = mapped_column(String(100))
    invoice_number: Mapped[str | None] = mapped_column(String(30))
    invoice_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(20), server_default=text("'web'"))

    refund: Mapped[RefundModel | None] = relationship(
        back_populates="booking", cascade="all, delete-orphan", lazy="selectin", uselist=False
    )

    __mapper_args__ = {"version_id_col": VersionMixin.version}  # noqa: RUF012

    __table_args__ = (
        UniqueConstraint("reference", name="uq_bookings_reference"),
        UniqueConstraint("invoice_number", name="uq_bookings_invoice_number"),
        CheckConstraint(
            "status IN ('pending_payment','pending_approval','confirmed','in_stay',"
            "'completed','cancelled','expired','rejected','no_show')",
            name="status_valid",
        ),
        CheckConstraint("check_out > check_in", name="dates_ordered"),
        CheckConstraint("adults >= 1", name="at_least_one_adult"),
        CheckConstraint("rooms >= 1", name="at_least_one_room"),
        # The money invariant, enforced by the database. The aggregate checks
        # it too, but only for writes that go through the aggregate.
        CheckConstraint(
            "total_minor = accommodation_minor + extra_guest_minor + cleaning_fee_minor "
            "+ tax_minor + platform_fee_minor",
            name="total_is_sum_of_parts",
        ),
        CheckConstraint("total_minor >= 0", name="total_non_negative"),
        CheckConstraint(
            "confirmed_at IS NULL OR payment_id IS NOT NULL", name="confirmed_needs_payment"
        ),
        # The guest's own history, newest first.
        Index("ix_bookings_guest", "guest_id", text("created_at DESC")),
        # The vendor's arrivals view.
        Index("ix_bookings_vendor_dates", "vendor_id", "check_in", "status"),
        Index("ix_bookings_property_dates", "property_id", "check_in"),
        # The expiry job: only rows that can actually expire. Partial, because
        # holds are a tiny and short-lived fraction of the table.
        Index(
            "ix_bookings_expiring",
            "hold_expires_at",
            postgresql_where=text("status IN ('pending_payment','pending_approval')"),
        ),
        # The daily check-in and completion sweeps.
        Index(
            "ix_bookings_active_stays",
            "check_out",
            "check_in",
            postgresql_where=text("status IN ('confirmed','in_stay')"),
        ),
        # Overlap questions over a room type — "what touches this week?" — as
        # one GiST lookup.
        Index("ix_bookings_stay_range", "room_type_id", "stay_range", postgresql_using="gist"),
    )


class RefundModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A refund in flight.

    One row per booking, enforced by a unique constraint. Refunding twice is
    real money leaving twice, and a retried webhook racing an impatient support
    agent is exactly how it happens.
    """

    __tablename__ = "booking_refunds"

    booking_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    #: The full itemisation, so "why did I only get 50% back?" is answerable
    #: from the row rather than by re-running the policy against dates that
    #: have since passed.
    breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    gateway_refund_id: Mapped[str | None] = mapped_column(String(100))
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # `raise_on_sql`, not the default `select`. This is the parent side of
    # a back-reference and is almost never wanted — the child is already
    # loaded, so touching it emits a second query nobody asked for. Under
    # asyncio the default does not even do that: it raises
    # `MissingGreenlet`, at runtime, with a message that names the
    # greenlet and not the attribute. This raises immediately and says
    # which relationship needs an explicit `selectinload`.
    booking: Mapped[BookingModel] = relationship(back_populates="refund", lazy="raise_on_sql")

    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_booking_refunds_booking"),
        CheckConstraint(
            "status IN ('pending','processing','completed','failed')", name="status_valid"
        ),
        CheckConstraint("amount_minor > 0", name="amount_positive"),
        # The retry queue for the refund worker.
        Index(
            "ix_booking_refunds_pending",
            "requested_at",
            postgresql_where=text("status IN ('pending','failed')"),
        ),
    )


class InvoiceSequenceModel(Base):
    """Gapless per-financial-year counters.

    **Not a Postgres SEQUENCE.** Sequences are explicitly non-transactional:
    they do not roll back, so every failed transaction burns a number and
    leaves a gap. Indian GST rules require consecutive invoice numbering, and a
    gap has to be explained to an auditor.

    A counter row incremented under ``SELECT … FOR UPDATE`` inside the same
    transaction as the invoice gives up concurrency — invoice creation
    serialises on this row — in exchange for the guarantee. That is the right
    trade here: this runs on booking confirmation, not on search, and the row
    is held for microseconds.
    """

    __tablename__ = "invoice_sequences"

    #: e.g. ``2026-27``. India's financial year runs April-March, so an invoice
    #: issued in January belongs to the year that started the previous April.
    financial_year: Mapped[str] = mapped_column(String(7), primary_key=True)
    series: Mapped[str] = mapped_column(String(10), primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (CheckConstraint("last_number >= 0", name="non_negative"),)
