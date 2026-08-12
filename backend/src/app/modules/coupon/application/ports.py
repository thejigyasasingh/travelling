"""What the coupon use cases need from persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from app.core.types.money import Money
from app.modules.coupon.domain.entities import Coupon


class CouponRepository(Protocol):
    async def get(self, coupon_id: uuid.UUID) -> Coupon | None: ...

    async def get_by_code(self, code: str) -> Coupon | None: ...

    async def add(self, coupon: Coupon) -> None: ...

    async def count_user_redemptions(self, coupon_id: uuid.UUID, user_id: uuid.UUID) -> int:
        """Counted from the redemption rows, never from a cached number."""
        ...

    async def claim(
        self,
        *,
        coupon: Coupon,
        booking_id: uuid.UUID,
        user_id: uuid.UUID,
        discount: Money,
        now: datetime,
    ) -> bool:
        """Atomically take one redemption. `False` means it was already gone.

        The guarantee lives in the database — a conditional UPDATE plus a unique
        constraint — because an in-memory counter cannot survive two people
        redeeming the last code at the same instant.
        """
        ...

    async def release(
        self, *, coupon_id: uuid.UUID, booking_id: uuid.UUID, now: datetime
    ) -> None: ...

    async def list_for_admin(
        self,
        *,
        status: str | None = None,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Coupon], int]: ...

    async def usage_summary(self, coupon_id: uuid.UUID) -> dict[str, int]: ...
