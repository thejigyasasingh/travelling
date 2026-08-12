"""Coupon value objects."""

from __future__ import annotations

from enum import StrEnum


class DiscountType(StrEnum):
    #: `value` is basis points — 2000 is 20%. Integers, because a float
    #: percentage on a large booking rounds differently on two machines.
    PERCENT = "percent"
    #: `value` is minor units. A flat ₹500 off is 50000.
    FLAT = "flat"


class CouponStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    #: Set by a scheduled job once `ends_at` passes, so the admin list can be
    #: filtered without every query re-deriving expiry from timestamps.
    EXPIRED = "expired"
