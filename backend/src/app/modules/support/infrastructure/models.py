"""Support persistence.

Messages sit in one table with an `is_internal` flag rather than two tables.
Two tables guarantee that one day a query forgets the filter and an internal
note is rendered to the guest; one table with an explicit flag makes the
dangerous case the one a developer has to opt into.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin


class TicketModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin):
    __tablename__ = "support_tickets"

    reference: Mapped[str] = mapped_column(String(16), nullable=False)
    #: Null for someone who wrote in without an account — which happens most
    #: often precisely when something has gone wrong with signing in.
    requester_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    requester_name: Mapped[str] = mapped_column(String(120), nullable=False)
    requester_email: Mapped[str] = mapped_column(String(320), nullable=False)

    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'open'"))

    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL")
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    #: Recorded, not derived. SLA reporting needs one authoritative answer to
    #: "when did a human first reply", and internal notes do not count.
    first_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(Text)

    messages: Mapped[list[TicketMessageModel]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TicketMessageModel.sent_at",
    )

    __mapper_args__ = {"version_id_col": VersionMixin.version}  # noqa: RUF012

    __table_args__ = (
        UniqueConstraint("reference", name="uq_tickets_reference"),
        CheckConstraint(
            "status IN ('open','in_progress','waiting_on_guest','resolved','closed')",
            name="status_valid",
        ),
        CheckConstraint("priority IN ('urgent','high','normal','low')", name="priority_valid"),
        CheckConstraint(
            "status <> 'resolved' OR resolution IS NOT NULL", name="resolved_needs_resolution"
        ),
        # The agent queue: unresolved tickets, worst priority first. Partial,
        # because a support desk's open set is a rounding error against its
        # history.
        Index(
            "ix_tickets_queue",
            "priority",
            "opened_at",
            postgresql_where=text("status IN ('open','in_progress','waiting_on_guest')"),
        ),
        # "What have I got?" — the second query every agent runs.
        Index(
            "ix_tickets_assigned",
            "assigned_to",
            "status",
            postgresql_where=text("assigned_to IS NOT NULL"),
        ),
        Index("ix_tickets_requester", "requester_email", "opened_at"),
        # Tickets attached to a booking, for the booking detail screen.
        Index("ix_tickets_booking", "booking_id", postgresql_where=text("booking_id IS NOT NULL")),
    )


class TicketMessageModel(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "support_ticket_messages"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    author_name: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    #: True for a note between agents. Never rendered to the requester.
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticket: Mapped[TicketModel] = relationship(back_populates="messages", lazy="raise_on_sql")

    __table_args__ = (Index("ix_ticket_messages_thread", "ticket_id", "sent_at"),)
