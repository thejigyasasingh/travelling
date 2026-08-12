"""What the admin use cases need from the read side.

A protocol rather than the concrete `AdminQueries`, for the same reason every
other module has ports: the use case states what it needs, the infrastructure
supplies it, and the dependency points inward. It also means a dashboard test
can hand over an object literal with six methods instead of a database.

Only reads appear here. The admin module deliberately owns no writes — every
action goes through the owning module's use case so its invariants still run.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

from app.modules.admin.application.dto import (
    Kpi,
    RevenueBreakdown,
    TimeSeriesPoint,
    TopProperty,
)


class AdminReadModel(Protocol):
    """The cross-module projections the dashboard and analytics screens read."""

    async def kpis(self, *, window_days: int = 30) -> list[Kpi]: ...

    async def action_queue(self) -> dict[str, int]:
        """What needs a human right now. The only part of the dashboard that is
        a to-do list rather than a report."""
        ...

    async def bookings_by_day(self, *, days: int = 30) -> list[TimeSeriesPoint]: ...

    async def revenue_by_day(self, *, days: int = 30) -> list[TimeSeriesPoint]: ...

    async def booking_status_mix(self, *, days: int = 30) -> dict[str, int]: ...

    async def top_properties(self, *, days: int = 30, limit: int = 5) -> list[TopProperty]: ...

    async def revenue_breakdown(self, *, from_date: date, to_date: date) -> RevenueBreakdown: ...

    async def analytics_extras(self, *, from_date: date, to_date: date) -> dict[str, Any]: ...

    async def bookings_by_city(
        self, *, from_date: date, to_date: date, limit: int = 10
    ) -> list[tuple[str, int, int]]: ...

    async def bookings_by_property_type(
        self, *, from_date: date, to_date: date
    ) -> dict[str, int]: ...
