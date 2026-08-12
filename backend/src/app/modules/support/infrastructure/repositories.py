"""Support persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.support.domain.entities import Ticket, TicketMessage
from app.modules.support.domain.value_objects import (
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.modules.support.infrastructure.models import TicketMessageModel, TicketModel

#: No 0/O/1/I/L: references are read aloud to agents over the phone by people
#: who are already annoyed.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"

#: Mirrors `TicketPriority.rank`, expressed in SQL so the database can order the
#: queue from an index rather than the application loading it all to sort.
_PRIORITY_RANK = case(
    {"urgent": 0, "high": 1, "normal": 2, "low": 3},
    value=TicketModel.priority,
    else_=9,
)


def _to_domain(row: TicketModel) -> Ticket:
    return Ticket(
        entity_id=row.id,
        reference=row.reference,
        requester_id=row.requester_id,
        requester_name=row.requester_name,
        requester_email=row.requester_email,
        subject=row.subject,
        category=TicketCategory(row.category),
        priority=TicketPriority(row.priority),
        status=TicketStatus(row.status),
        opened_at=row.opened_at,
        booking_id=row.booking_id,
        assigned_to=row.assigned_to,
        first_responded_at=row.first_responded_at,
        resolved_at=row.resolved_at,
        closed_at=row.closed_at,
        resolution=row.resolution,
        messages=[
            TicketMessage(
                entity_id=m.id,
                author_id=m.author_id,
                author_name=m.author_name,
                body=m.body,
                sent_at=m.sent_at,
                is_internal=m.is_internal,
            )
            for m in row.messages
        ],
        version=row.version,
    )


class SqlTicketRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._identity: dict[uuid.UUID, tuple[Ticket, TicketModel]] = {}

    async def get(self, ticket_id: uuid.UUID) -> Ticket | None:
        if ticket_id in self._identity:
            return self._identity[ticket_id][0]
        return self._track(await self._session.get(TicketModel, ticket_id))

    async def get_by_reference(self, reference: str) -> Ticket | None:
        row = (
            await self._session.execute(
                select(TicketModel).where(TicketModel.reference == reference.strip().upper())
            )
        ).scalar_one_or_none()
        return self._track(row)

    async def add(self, ticket: Ticket) -> None:
        row = TicketModel(
            id=ticket.id,
            reference=ticket.reference,
            requester_id=ticket.requester_id,
            requester_name=ticket.requester_name,
            requester_email=ticket.requester_email,
            subject=ticket.subject,
            category=ticket.category.value,
            priority=ticket.priority.value,
            status=ticket.status.value,
            booking_id=ticket.booking_id,
            opened_at=ticket.opened_at,
        )
        self._session.add(row)
        self._identity[ticket.id] = (ticket, row)

    async def list_for_requester(
        self, *, user_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> tuple[list[Ticket], int]:
        stmt = (
            select(TicketModel)
            .where(TicketModel.requester_id == user_id)
            .order_by(TicketModel.opened_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        total = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(TicketModel)
                    .where(TicketModel.requester_id == user_id)
                )
            ).scalar()
            or 0
        )
        return [t for t in (self._track(r) for r in rows) if t is not None], total

    async def list_for_admin(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        assigned_to: uuid.UUID | None = None,
        unassigned_only: bool = False,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Ticket], int]:
        """The agent queue.

        Sorted by priority then age, because an urgent ticket opened five
        minutes ago matters more than a low one from yesterday — the reverse of
        what a plain reverse-chronological list would show.
        """
        stmt = select(TicketModel)
        count_stmt = select(func.count()).select_from(TicketModel)

        def both(condition: Any) -> None:
            nonlocal stmt, count_stmt
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        if status == "open":
            both(TicketModel.status.in_(["open", "in_progress", "waiting_on_guest"]))
        elif status:
            both(TicketModel.status == status)
        if priority:
            both(TicketModel.priority == priority)
        if assigned_to is not None:
            both(TicketModel.assigned_to == assigned_to)
        if unassigned_only:
            both(TicketModel.assigned_to.is_(None))
        if query:
            pattern = f"%{query.lower()}%"
            both(
                func.lower(TicketModel.subject).like(pattern)
                | func.lower(TicketModel.requester_email).like(pattern)
                | (TicketModel.reference == query.strip().upper())
            )

        stmt = stmt.order_by(_PRIORITY_RANK, TicketModel.opened_at).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        return [t for t in (self._track(r) for r in rows) if t is not None], total

    async def queue_counts(self) -> dict[str, int]:
        """The numbers on the dashboard tile."""
        rows = (
            await self._session.execute(
                select(TicketModel.status, func.count()).group_by(TicketModel.status)
            )
        ).all()
        return {str(status): int(count) for status, count in rows}

    async def flush(self) -> None:
        for ticket, row in self._identity.values():
            row.status = ticket.status.value
            row.priority = ticket.priority.value
            row.assigned_to = ticket.assigned_to
            row.first_responded_at = ticket.first_responded_at
            row.resolved_at = ticket.resolved_at
            row.closed_at = ticket.closed_at
            row.resolution = ticket.resolution

            known = {m.id for m in row.messages}
            for message in ticket.messages:
                if message.id in known:
                    continue
                row.messages.append(
                    TicketMessageModel(
                        id=message.id,
                        ticket_id=ticket.id,
                        author_id=message.author_id,
                        author_name=message.author_name,
                        body=message.body,
                        is_internal=message.is_internal,
                        sent_at=message.sent_at,
                    )
                )
        await self._session.flush()

    def pending_events(self) -> list[Any]:
        events: list[Any] = []
        for ticket, _ in self._identity.values():
            events.extend(ticket.pull_events())
        return events

    def _track(self, row: TicketModel | None) -> Ticket | None:
        if row is None:
            return None
        if row.id in self._identity:
            return self._identity[row.id][0]
        ticket = _to_domain(row)
        self._identity[row.id] = (ticket, row)
        return ticket


def resolution_stats(rows: list[tuple[datetime, datetime | None]]) -> dict[str, float]:
    """Median-ish SLA numbers for the dashboard, computed in Python.

    A percentile in SQL means a window function over the whole ticket history
    on every dashboard load; the open set is small enough that this is cheaper
    and far easier to read.
    """
    durations = [
        (responded - opened).total_seconds() / 3600
        for opened, responded in rows
        if responded is not None
    ]
    if not durations:
        return {"count": 0, "average_hours": 0.0, "median_hours": 0.0}
    ordered = sorted(durations)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return {
        "count": len(ordered),
        "average_hours": round(sum(ordered) / len(ordered), 2),
        "median_hours": round(median, 2),
    }
