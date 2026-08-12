"""Coupon HTTP schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreateCouponRequest(BaseModel):
    code: str = Field(min_length=3, max_length=24)
    description: str = Field(default="", max_length=200)
    discount_type: Literal["percent", "flat"]
    #: Basis points for a percentage (2000 = 20%), minor units for a flat
    #: amount (50000 = ₹500).
    value: int = Field(gt=0)
    starts_at: datetime
    ends_at: datetime
    min_booking_minor: int = Field(default=0, ge=0)
    #: Required for a percentage. An uncapped 20% on a ₹4,00,000 villa week is
    #: ₹80,000, which is the most expensive mistake this endpoint can make.
    max_discount_minor: int | None = Field(default=None, gt=0)
    total_limit: int | None = Field(default=None, ge=1)
    per_user_limit: int = Field(default=1, ge=1, le=50)
    first_booking_only: bool = False
    property_ids: list[uuid.UUID] = Field(default_factory=list)


class CouponResponse(BaseModel):
    id: uuid.UUID
    code: str
    description: str
    discount_type: str
    value: int
    status: str
    starts_at: datetime
    ends_at: datetime
    min_booking_minor: int
    max_discount_minor: int | None = None
    total_limit: int | None = None
    per_user_limit: int
    first_booking_only: bool
    redeemed_count: int
    #: `null` means unlimited, which is different from zero.
    remaining: int | None = None
    property_ids: list[uuid.UUID] = Field(default_factory=list)


class CouponUsageResponse(BaseModel):
    redemptions: int
    released: int
    discount_minor: int


class CouponListResponse(BaseModel):
    items: list[CouponResponse]
    total: int
    page: int
    size: int


class PreviewCouponRequest(BaseModel):
    code: str = Field(min_length=3, max_length=24)
    property_id: uuid.UUID
    accommodation_minor: int = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)


class CouponPreviewResponse(BaseModel):
    code: str
    description: str
    discount_minor: int
    currency: str
    #: What the guest would pay for accommodation after the discount. Tax is
    #: unchanged — it is collected on what is actually charged.
    accommodation_after_minor: int


class SetCouponStatusRequest(BaseModel):
    active: bool
