"""Admin use cases.

Two kinds live here and they are kept visibly apart:

**Reads** compose the cross-module projections in `infrastructure/queries.py`.

**Actions** delegate to the *owning* module's use case — approving a vendor
calls the vendor module, suspending a property calls the property module. The
admin module never writes to another module's tables. An admin action that
bypassed the owning aggregate would skip its invariants, its events and its
audit trail, which is precisely the failure mode an admin panel is famous for.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.core.clock import Clock
from app.core.logging import get_logger
from app.modules.admin.application.dto import AnalyticsView, DashboardView
from app.modules.admin.application.ports import AdminReadModel
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

#: A dashboard is a glance, not a report. Ninety days of daily points is 90
#: pixels of chart nobody reads and a scan the database feels.
MAX_WINDOW_DAYS = 90


@dataclass(slots=True)
class GetDashboard:
    """Everything on the landing screen, in one call.

    Assembled server-side rather than by six parallel requests from the client:
    the tiles have to agree with each other, and six queries issued at slightly
    different moments do not.
    """

    queries: AdminReadModel
    clock: Clock

    async def execute(self, window_days: int, actor: Actor) -> DashboardView:
        days = max(1, min(window_days, MAX_WINDOW_DAYS))

        return DashboardView(
            kpis=await self.queries.kpis(window_days=days),
            bookings_by_day=await self.queries.bookings_by_day(days=days),
            revenue_by_day=await self.queries.revenue_by_day(days=days),
            booking_status_mix=await self.queries.booking_status_mix(days=days),
            top_properties=await self.queries.top_properties(days=days),
            action_queue=await self.queries.action_queue(),
            generated_at=self.clock.now(),
        )


@dataclass(slots=True)
class GetAnalytics:
    queries: AdminReadModel
    clock: Clock

    async def execute(
        self, from_date: date | None, to_date: date | None, actor: Actor
    ) -> AnalyticsView:
        today = self.clock.now().date()
        end = to_date or today
        start = from_date or (end - timedelta(days=29))

        # Clamped rather than rejected: an admin who types a two-year range
        # wants a report, and quietly narrowing it beats a validation error —
        # but an unbounded aggregate over `bookings` is how a dashboard takes
        # the site down.
        if (end - start).days > MAX_WINDOW_DAYS:
            start = end - timedelta(days=MAX_WINDOW_DAYS)
            logger.info("analytics_window_clamped", days=MAX_WINDOW_DAYS)

        revenue = await self.queries.revenue_breakdown(from_date=start, to_date=end)
        extras = await self.queries.analytics_extras(from_date=start, to_date=end)

        return AnalyticsView(
            revenue=revenue,
            bookings_by_day=await self.queries.bookings_by_day(days=(end - start).days + 1),
            revenue_by_day=await self.queries.revenue_by_day(days=(end - start).days + 1),
            by_city=await self.queries.bookings_by_city(from_date=start, to_date=end),
            by_property_type=await self.queries.bookings_by_property_type(
                from_date=start, to_date=end
            ),
            cancellation_rate=float(extras["cancellation_rate"]),
            average_booking_value_minor=int(extras["average_booking_value_minor"]),
            average_lead_time_days=float(extras["average_lead_time_days"]),
            occupancy_percent=float(extras["occupancy_percent"]),
            coupon_cost_minor=revenue.discounts_minor,
            top_properties=await self.queries.top_properties(days=(end - start).days + 1, limit=10),
        )
