"""Coupon events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

from app.shared.domain.events import DomainEvent

AGGREGATE = "coupon"


@dataclass(frozen=True, kw_only=True)
class CouponRedeemed(DomainEvent):
    """Every discount granted, as a fact.

    Marketing reconciles campaign spend against these, and finance needs them
    to explain why revenue and gross bookings differ.
    """

    event_type: ClassVar[str] = "coupon.redeemed"
    aggregate_type: ClassVar[str] = AGGREGATE

    code: str
    booking_id: uuid.UUID
    user_id: uuid.UUID
    discount_minor: int
    currency: str
    redeemed_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "coupon_id": str(self.aggregate_id),
            "code": self.code,
            "booking_id": str(self.booking_id),
            "user_id": str(self.user_id),
            "discount_minor": self.discount_minor,
            "currency": self.currency,
            "redeemed_at": self.redeemed_at.isoformat(),
        }
