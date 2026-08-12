"""The AI transaction scope.

Two sessions, not one, and that is the whole point of this file.

Retrieval reads across bookings, properties and reviews to build a candidate
set. Those are analytical queries — self-joins over booking history, aggregates
over 90-day windows — and running them on the primary puts a recommendation
rail in competition with checkout. They go to the **replica**.

Writes go to the **primary**, because a review insight written to a replica is
a review insight that does not exist.

Nothing here spans both. A use case reads candidates and writes derived rows,
and there is no invariant connecting the two — which is exactly why the split
is safe here and would not be inside the booking module.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.infrastructure.candidates import SqlCandidateSource
from app.modules.ai.infrastructure.repositories import AIRepository


class AIUow:
    def __init__(self, session: AsyncSession, *, read_session: AsyncSession | None = None) -> None:
        self.session = session
        self.store = AIRepository(session)
        # Falls back to the write session when no replica is configured, so a
        # single-database deployment works without a code path of its own.
        self.candidates = SqlCandidateSource(read_session or session)

    async def flush(self) -> None:
        await self.store.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    def pending_events(self) -> list[Any]:
        """Nothing here emits domain events.

        Derived data is not a fact about the business — a sentiment score is
        our guess about a review, and nothing downstream should react to it as
        though something happened. Present so the shape matches every other
        unit of work in the codebase.
        """
        return []
