"""Admin wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.interface.api.deps import ContainerDep
from app.modules.admin.application.use_cases import GetAnalytics, GetDashboard
from app.modules.admin.infrastructure.queries import AdminQueries


async def get_read_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    """Reads go to the **replica**, unlike everything else in this codebase.

    An admin dashboard runs aggregates over the whole booking history. Pointing
    those at the primary means a report someone runs at 9am competes with
    checkout for connections. Replication lag of a second or two is irrelevant
    to a 30-day revenue chart, and very relevant to a booking.
    """
    async with container.database.read_session() as session:
        yield session


ReadSessionDep = Annotated[AsyncSession, Depends(get_read_session)]


def admin_queries(session: ReadSessionDep) -> AdminQueries:
    return AdminQueries(session)


AdminQueriesDep = Annotated[AdminQueries, Depends(admin_queries)]


def dashboard_uc(container: ContainerDep, queries: AdminQueriesDep) -> GetDashboard:
    return GetDashboard(queries=queries, clock=container.clock)


def analytics_uc(container: ContainerDep, queries: AdminQueriesDep) -> GetAnalytics:
    return GetAnalytics(queries=queries, clock=container.clock)
