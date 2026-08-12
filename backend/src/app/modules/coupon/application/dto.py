"""Coupon inputs.

Typed rather than `dict[str, Any]`. A dict at a use-case boundary means every
field is `object` inside, so the type checker cannot tell a date from a string
and every read needs a cast — which is exactly where a wrong field name lives
undetected until runtime.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateCouponInput:
    code: str
    description: str
    discount_type: str
    #: Basis points for a percentage, minor units for a flat amount.
    value: int
    starts_at: datetime
    ends_at: datetime
    min_booking_minor: int = 0
    max_discount_minor: int | None = None
    total_limit: int | None = None
    per_user_limit: int = 1
    first_booking_only: bool = False
    property_ids: list[uuid.UUID] = field(default_factory=list)
