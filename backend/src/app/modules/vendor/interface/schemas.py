"""Vendor HTTP schemas."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class RegisterVendorRequest(BaseModel):
    legal_name: str = Field(min_length=3, max_length=200)
    display_name: str = Field(default="", max_length=120)
    contact_email: str = Field(max_length=320)
    contact_phone: str = Field(max_length=20)
    #: Validated for shape here and for authenticity by a human at review.
    gstin: str | None = Field(default=None, min_length=15, max_length=15)
    pan: str | None = Field(default=None, min_length=10, max_length=10)


class VendorResponse(BaseModel):
    id: uuid.UUID
    legal_name: str
    display_name: str
    contact_email: str
    contact_phone: str
    status: str
    gstin: str | None = None
    pan: str | None = None
    #: Last four digits only — the full number never reaches this service.
    bank_account_last4: str | None = None
    bank_ifsc: str | None = None
    commission_bps: int
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    suspension_reason: str | None = None
    can_publish: bool
    can_receive_payouts: bool


class UpdateBankRequest(BaseModel):
    #: Deliberately last-4 only. A full account number would put this service
    #: in the business of guarding bank credentials.
    account_last4: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    ifsc: str = Field(min_length=11, max_length=11)


# ══════════════════════════════════════════════════════════════════════════
# Reporting
# ══════════════════════════════════════════════════════════════════════════


class VendorDashboardResponse(BaseModel):
    live_listings: int
    in_review: int
    awaiting_approval: int
    arrivals_this_week: int
    in_stay: int
    gross_30d_minor: int
    commission_30d_minor: int
    #: What the vendor is actually paid. Shown beside gross rather than instead
    #: of it — a host who only sees gross is a host who queries every payout.
    net_30d_minor: int
    reviews_awaiting: int


class EarningsResponse(BaseModel):
    gross_minor: int
    commission_minor: int
    #: Remitted to the government, not earned. Shown so a host can reconcile
    #: their GST filing, and excluded from what they are paid.
    tax_collected_minor: int
    refunded_minor: int
    net_payable_minor: int
    bookings: int
    nights_sold: int
    average_booking_minor: int
    average_nightly_minor: int
    currency: str = "INR"
    from_date: date
    to_date: date


class RevenuePointResponse(BaseModel):
    day: date
    revenue_minor: int
    bookings: int


class PropertyPerformanceResponse(BaseModel):
    property_id: uuid.UUID
    name: str
    city: str
    status: str
    bookings: int
    gross_minor: int
    nights_sold: int
    review_average: float
    review_count: int


class OccupancyResponse(BaseModel):
    nights_booked: int
    nights_available: int
    occupancy_percent: float


class ArrivalResponse(BaseModel):
    booking_id: uuid.UUID
    reference: str
    guest_name: str
    guest_phone: str
    property_name: str
    room_type_name: str
    check_in: date
    check_out: date
    guests: int
    status: str
    total_minor: int
    currency: str


class MonthlyStatementRow(BaseModel):
    month: date
    bookings: int
    gross_minor: int
    commission_minor: int
    tax_minor: int
    net_minor: int


class ReportsResponse(BaseModel):
    earnings: EarningsResponse
    occupancy: OccupancyResponse
    by_property: list[PropertyPerformanceResponse]
    monthly: list[MonthlyStatementRow]
    revenue_by_day: list[RevenuePointResponse]
