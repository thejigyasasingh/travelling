"""Transactional outbox.

The model + writer only. The relay (Celery Beat, `SELECT ... FOR UPDATE SKIP
LOCKED`, every second) lands with the queue module.

Why this exists at all: without it, event publication is
``commit(); task.delay(...)``. A crash in that window — a deploy, an OOM kill,
a spot reclaim — leaves a confirmed booking whose confirmation email was never
sent, or whose payout was never scheduled, with no way to detect it afterwards.
Writing the event in the same transaction reduces the worst case to *delayed*
delivery, which is recoverable and observable.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Index, SmallInteger, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.logging import request_id_var, trace_id_var
from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.unit_of_work import DomainEvent


class OutboxEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "outbox"

    aggregate_type: Mapped[str] = mapped_column(String(40), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    # Consumers may be deployed independently of producers, so the payload is
    # a versioned snapshot rather than an ID to re-read. Re-reading races: an
    # event processed 30s late must see the state as it was when published.
    event_version: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("1")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # Partial index: the relay polls every second, forever. Processed rows
        # run to millions before archival; a full index would grow without
        # bound. Partial keeps it roughly the size of the pending backlog —
        # a few hundred rows, permanently in cache.
        Index(
            "ix_outbox_pending",
            "created_at",
            postgresql_where=text("processed_at IS NULL AND attempts < 10"),
        ),
        Index("ix_outbox_aggregate", "aggregate_type", "aggregate_id"),
    )


async def persist_events(session: AsyncSession, events: Sequence[DomainEvent]) -> None:
    """Append events to the outbox **without committing**.

    The caller's transaction owns the commit — that is the entire point.
    """
    if not events:
        return

    rid = request_id_var.get()
    tid = trace_id_var.get()

    session.add_all(
        [
            OutboxEvent(
                aggregate_type=e.aggregate_type,
                aggregate_id=e.aggregate_id,
                event_type=e.event_type,
                payload=e.to_payload(),
                trace_id=tid,
                request_id=rid,
            )
            for e in events
        ]
    )
