"""Admin read models.

Flat, denormalised, and shaped for a screen. Deliberately **not** the domain
aggregates: an admin list renders fifty rows with a joined vendor name and a
booking count, and loading fifty aggregates plus their children to render a
table is how an admin panel becomes the slowest page in the product.

These are read-only projections. Nothing here mutates; every admin action goes
through the owning module's own use case, so its invariants still run.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class Kpi:
    """One dashboard number, with its comparison.

    The delta is carried alongside rather than computed in the UI: "₹4.2L" means
    nothing without "up 12% on last week", and two clients computing that from
    two queries will eventually disagree.
    """

    key: str
    label: str
    value: int
    #: Percentage change against the preceding equal-length window. `None` when
    #: there is no prior data — which is different from 0% and must not render
    #: as "no change".
    change_percent: float | None = None
    unit: str = "count"


@dataclass(frozen=True, slots=True)
class TimeSeriesPoint:
    day: date
    value: int


@dataclass(frozen=True, slots=True)
class DashboardView:
    kpis: list[Kpi]
    bookings_by_day: list[TimeSeriesPoint]
    revenue_by_day: list[TimeSeriesPoint]
    booking_status_mix: dict[str, int]
    top_properties: list[TopProperty]
    #: What needs a human right now, and how many of each.
    action_queue: dict[str, int]
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class TopProperty:
    property_id: uuid.UUID
    name: str
    city: str
    bookings: int
    revenue_minor: int
    currency: str


@dataclass(frozen=True, slots=True)
class AdminUserRow:
    id: uuid.UUID
    email: str
    full_name: str | None
    phone: str | None
    status: str
    roles: list[str]
    email_verified: bool
    created_at: datetime | None
    last_login_at: datetime | None
    booking_count: int
    lifetime_value_minor: int
    currency: str


@dataclass(frozen=True, slots=True)
class AdminPropertyRow:
    id: uuid.UUID
    name: str
    slug: str
    city: str
    property_type: str
    status: str
    vendor_id: uuid.UUID
    vendor_name: str | None
    room_types: int
    review_average: float
    review_count: int
    created_at: datetime | None
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class AdminBookingRow:
    id: uuid.UUID
    reference: str
    status: str
    guest_name: str
    guest_email: str
    property_id: uuid.UUID
    property_name: str
    check_in: date
    check_out: date
    nights: int
    total_minor: int
    currency: str
    created_at: datetime | None
    has_open_ticket: bool


@dataclass(frozen=True, slots=True)
class AdminPaymentRow:
    id: uuid.UUID
    booking_reference: str
    status: str
    method: str
    amount_minor: int
    refunded_minor: int
    #: `sum(ledger)` — what the platform actually holds after fees and refunds.
    net_minor: int
    currency: str
    created_at: datetime | None
    captured_at: datetime | None


@dataclass(frozen=True, slots=True)
class AdminVendorRow:
    id: uuid.UUID
    legal_name: str
    display_name: str
    contact_email: str
    status: str
    commission_bps: int
    property_count: int
    published_count: int
    gross_bookings_minor: int
    currency: str
    created_at: datetime | None
    approved_at: datetime | None


@dataclass(frozen=True, slots=True)
class PagedResult[T]:
    """Offset-paged, unlike the guest-facing lists.

    An admin table is a bounded internal set that people page through by number
    and sort by column. Cursor paging would make "page 4" unexpressible and is
    optimising for a scale these tables will not reach.
    """

    items: list[T]
    total: int
    page: int
    size: int

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.size))


@dataclass(frozen=True, slots=True)
class RevenueBreakdown:
    """Where the money went. The numbers finance reconciles against."""

    gross_minor: int
    refunded_minor: int
    gateway_fees_minor: int
    platform_commission_minor: int
    vendor_payable_minor: int
    tax_collected_minor: int
    discounts_minor: int
    currency: str
    from_date: date
    to_date: date

    @property
    def net_minor(self) -> int:
        return self.gross_minor - self.refunded_minor


@dataclass(frozen=True, slots=True)
class AnalyticsView:
    revenue: RevenueBreakdown
    bookings_by_day: list[TimeSeriesPoint]
    revenue_by_day: list[TimeSeriesPoint]
    by_city: list[tuple[str, int, int]]
    by_property_type: dict[str, int]
    cancellation_rate: float
    average_booking_value_minor: int
    average_lead_time_days: float
    occupancy_percent: float
    coupon_cost_minor: int
    top_properties: list[TopProperty] = field(default_factory=list)
