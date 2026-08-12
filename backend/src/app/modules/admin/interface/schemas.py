"""Admin HTTP schemas.

Money is integer minor units on the wire, as everywhere else. Percentages are
floats because they are already derived numbers with no arithmetic left to do.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class KpiResponse(BaseModel):
    key: str
    label: str
    value: int
    #: `null` means "no prior data", which is different from 0% and must not be
    #: rendered as "no change".
    change_percent: float | None = None
    unit: str = "count"


class TimeSeriesPointResponse(BaseModel):
    day: date
    value: int


class TopPropertyResponse(BaseModel):
    property_id: uuid.UUID
    name: str
    city: str
    bookings: int
    revenue_minor: int
    currency: str


class DashboardResponse(BaseModel):
    kpis: list[KpiResponse]
    bookings_by_day: list[TimeSeriesPointResponse]
    revenue_by_day: list[TimeSeriesPointResponse]
    booking_status_mix: dict[str, int]
    top_properties: list[TopPropertyResponse]
    action_queue: dict[str, int]
    generated_at: datetime


class RevenueBreakdownResponse(BaseModel):
    gross_minor: int
    refunded_minor: int
    net_minor: int
    gateway_fees_minor: int
    platform_commission_minor: int
    vendor_payable_minor: int
    tax_collected_minor: int
    discounts_minor: int
    currency: str
    from_date: date
    to_date: date


class CityBreakdownResponse(BaseModel):
    city: str
    bookings: int
    revenue_minor: int


class AnalyticsResponse(BaseModel):
    revenue: RevenueBreakdownResponse
    bookings_by_day: list[TimeSeriesPointResponse]
    revenue_by_day: list[TimeSeriesPointResponse]
    by_city: list[CityBreakdownResponse]
    by_property_type: dict[str, int]
    cancellation_rate: float
    average_booking_value_minor: int
    average_lead_time_days: float
    occupancy_percent: float
    coupon_cost_minor: int
    top_properties: list[TopPropertyResponse]


class PageMetaResponse(BaseModel):
    total: int
    page: int
    size: int
    pages: int


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None = None
    phone: str | None = None
    status: str
    roles: list[str]
    email_verified: bool
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    booking_count: int
    lifetime_value_minor: int
    currency: str


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    meta: PageMetaResponse


class AdminPropertyResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    city: str
    property_type: str
    status: str
    vendor_id: uuid.UUID
    vendor_name: str | None = None
    room_types: int
    review_average: float
    review_count: int
    created_at: datetime | None = None
    published_at: datetime | None = None


class AdminPropertyListResponse(BaseModel):
    items: list[AdminPropertyResponse]
    meta: PageMetaResponse


class AdminBookingResponse(BaseModel):
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
    created_at: datetime | None = None
    has_open_ticket: bool


class AdminBookingListResponse(BaseModel):
    items: list[AdminBookingResponse]
    meta: PageMetaResponse


class AdminPaymentResponse(BaseModel):
    id: uuid.UUID
    booking_reference: str
    status: str
    method: str
    amount_minor: int
    refunded_minor: int
    net_minor: int
    currency: str
    created_at: datetime | None = None
    captured_at: datetime | None = None


class AdminPaymentListResponse(BaseModel):
    items: list[AdminPaymentResponse]
    meta: PageMetaResponse


class AdminVendorResponse(BaseModel):
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
    created_at: datetime | None = None
    approved_at: datetime | None = None


class AdminVendorListResponse(BaseModel):
    items: list[AdminVendorResponse]
    meta: PageMetaResponse


class NotificationResponse(BaseModel):
    id: str
    channel: str
    template: str
    recipient: str
    subject: str | None = None
    preview: str | None = None
    status: str
    error: str | None = None
    attempts: int
    created_at: datetime | None = None
    sent_at: datetime | None = None


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    meta: PageMetaResponse


# ── requests ──────────────────────────────────────────────────────────────


class SuspendUserRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class ApproveVendorRequest(BaseModel):
    commission_bps: int | None = Field(default=None, ge=0, le=3000)


class RejectVendorRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class SuspendVendorRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
