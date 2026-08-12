"""The coupon transaction scope."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.outbox import persist_events
from app.modules.coupon.infrastructure.repositories import SqlCouponRepository


class CouponUow:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.coupons = SqlCouponRepository(session)

    async def flush(self) -> None:
        await self.coupons.flush()
        # A redemption and its event commit together, so a discount can never
        # exist without the fact that explains it in the campaign report.
        await persist_events(self.session, self.coupons.pending_events())

    async def commit(self) -> None:
        await self.flush()
        await self.session.commit()

    def pending_events(self) -> list[Any]:
        return self.coupons.pending_events()
