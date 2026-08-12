"""The support transaction scope."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.outbox import persist_events
from app.modules.support.infrastructure.repositories import SqlTicketRepository


class SupportUow:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tickets = SqlTicketRepository(session)

    async def flush(self) -> None:
        await self.tickets.flush()
        await persist_events(self.session, self.tickets.pending_events())

    async def commit(self) -> None:
        await self.flush()
        await self.session.commit()

    def pending_events(self) -> list[Any]:
        return self.tickets.pending_events()
