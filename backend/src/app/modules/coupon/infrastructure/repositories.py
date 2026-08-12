"""Coupon persistence, and the concurrency guard that makes limits real."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.types.money import Money
from app.modules.coupon.domain import errors
from app.modules.coupon.domain.entities import Coupon
from app.modules.coupon.domain.value_objects import CouponStatus, DiscountType
from app.modules.coupon.infrastructure.models import CouponModel, CouponRedemptionModel


def _to_domain(row: CouponModel) -> Coupon:
    return Coupon(
        entity_id=row.id,
        code=row.code,
        description=row.description,
        discount_type=DiscountType(row.discount_type),
        value=row.value,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        status=CouponStatus(row.status),
        min_booking_minor=row.min_booking_minor,
        max_discount_minor=row.max_discount_minor,
        total_limit=row.total_limit,
        per_user_limit=row.per_user_limit,
        first_booking_only=row.first_booking_only,
        applies_to_property_ids=frozenset(row.property_ids or []),
        redeemed_count=row.redeemed_count,
        version=row.version,
    )


#: Claim one redemption of a limited coupon.
#:
#: The `WHERE` clause is the entire guard. Reading the count and then writing
#: it back is a check-then-act race, and the losing side of that race gives
#: away a discount that was already spent. Here the database decides: the
#: UPDATE matches only while the coupon is live and under its limit, and
#: `rowcount == 0` means someone else took the last one.
_CLAIM_SQL = """
UPDATE coupons
   SET redeemed_count = redeemed_count + 1,
       updated_at     = now()
 WHERE id = :coupon_id
   AND status = 'active'
   AND now() BETWEEN starts_at AND ends_at
   AND (total_limit IS NULL OR redeemed_count < total_limit)
"""


class SqlCouponRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._identity: dict[uuid.UUID, tuple[Coupon, CouponModel]] = {}

    async def get(self, coupon_id: uuid.UUID) -> Coupon | None:
        if coupon_id in self._identity:
            return self._identity[coupon_id][0]
        return self._track(await self._session.get(CouponModel, coupon_id))

    async def get_by_code(self, code: str) -> Coupon | None:
        row = (
            await self._session.execute(
                select(CouponModel).where(CouponModel.code == code.strip().upper())
            )
        ).scalar_one_or_none()
        return self._track(row)

    async def add(self, coupon: Coupon) -> None:
        row = CouponModel(
            id=coupon.id,
            code=coupon.code,
            description=coupon.description,
            discount_type=coupon.discount_type.value,
            value=coupon.value,
            status=coupon.status.value,
            starts_at=coupon.starts_at,
            ends_at=coupon.ends_at,
            min_booking_minor=coupon.min_booking_minor,
            max_discount_minor=coupon.max_discount_minor,
            total_limit=coupon.total_limit,
            per_user_limit=coupon.per_user_limit,
            first_booking_only=coupon.first_booking_only,
            property_ids=list(coupon.applies_to_property_ids),
        )
        self._session.add(row)
        self._identity[coupon.id] = (coupon, row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # The unique index, not a prior SELECT: two admins creating the
            # same code at once both pass a check-then-act.
            raise errors.DuplicateCouponCodeError(coupon.code) from exc

    async def count_user_redemptions(self, coupon_id: uuid.UUID, user_id: uuid.UUID) -> int:
        """Counted from the redemption rows, never from a cached number.

        Released redemptions are excluded: a guest whose booking was cancelled
        gets their use of the code back.
        """
        return int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(CouponRedemptionModel)
                    .where(
                        CouponRedemptionModel.coupon_id == coupon_id,
                        CouponRedemptionModel.user_id == user_id,
                        CouponRedemptionModel.released_at.is_(None),
                    )
                )
            ).scalar()
            or 0
        )

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

        Two guards, because they fail differently: the conditional UPDATE stops
        the *last* code being spent twice, and the unique constraint on
        `(coupon_id, booking_id)` stops the *same* booking being discounted
        twice by a retry.
        """
        result = await self._session.execute(text(_CLAIM_SQL), {"coupon_id": coupon.id})
        if int(cast("CursorResult[Any]", result).rowcount or 0) == 0:
            return False

        self._session.add(
            CouponRedemptionModel(
                coupon_id=coupon.id,
                booking_id=booking_id,
                user_id=user_id,
                discount_minor=discount.amount_minor,
                currency=discount.currency,
                redeemed_at=now,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError:
            # Already redeemed for this booking. The claim above over-counted,
            # so it is handed back rather than left inflating the total.
            await self._session.rollback()
            return False
        return True

    async def release(self, *, coupon_id: uuid.UUID, booking_id: uuid.UUID, now: datetime) -> None:
        """Give a redemption back when a booking is cancelled.

        Marked rather than deleted: the fact that a code was used and then
        released is what explains a campaign report that does not add up.
        """
        await self._session.execute(
            text(
                "UPDATE coupon_redemptions SET released_at = :now "
                " WHERE coupon_id = :coupon_id AND booking_id = :booking_id "
                "   AND released_at IS NULL"
            ),
            {"now": now, "coupon_id": coupon_id, "booking_id": booking_id},
        )
        await self._session.execute(
            text(
                "UPDATE coupons SET redeemed_count = GREATEST(redeemed_count - 1, 0) "
                " WHERE id = :coupon_id"
            ),
            {"coupon_id": coupon_id},
        )

    async def list_for_admin(
        self,
        *,
        status: str | None = None,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Coupon], int]:
        stmt = select(CouponModel)
        count_stmt = select(func.count()).select_from(CouponModel)

        if status:
            stmt = stmt.where(CouponModel.status == status)
            count_stmt = count_stmt.where(CouponModel.status == status)
        if query:
            pattern = f"%{query.strip().upper()}%"
            stmt = stmt.where(CouponModel.code.like(pattern))
            count_stmt = count_stmt.where(CouponModel.code.like(pattern))

        stmt = stmt.order_by(CouponModel.created_at.desc()).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        return [c for c in (self._track(r) for r in rows) if c is not None], total

    async def usage_summary(self, coupon_id: uuid.UUID) -> dict[str, int]:
        """What the campaign actually cost."""
        row = (
            await self._session.execute(
                text(
                    "SELECT count(*) FILTER (WHERE released_at IS NULL)  AS redemptions, "
                    "       count(*) FILTER (WHERE released_at IS NOT NULL) AS released, "
                    "       COALESCE(sum(discount_minor) FILTER "
                    "                (WHERE released_at IS NULL), 0)     AS discount_minor "
                    "  FROM coupon_redemptions WHERE coupon_id = :coupon_id"
                ),
                {"coupon_id": coupon_id},
            )
        ).one()
        return {
            "redemptions": int(row[0] or 0),
            "released": int(row[1] or 0),
            "discount_minor": int(row[2] or 0),
        }

    async def expire_past_coupons(self, *, now: datetime) -> int:
        """Move lapsed coupons to `expired` so the admin list can filter on a
        column rather than re-deriving expiry from timestamps on every query."""
        result = await self._session.execute(
            text(
                "UPDATE coupons SET status = 'expired'  WHERE status = 'active' AND ends_at < :now"
            ),
            {"now": now},
        )
        return int(cast("CursorResult[Any]", result).rowcount or 0)

    async def flush(self) -> None:
        for coupon, row in self._identity.values():
            row.description = coupon.description
            row.status = coupon.status.value
            row.starts_at = coupon.starts_at
            row.ends_at = coupon.ends_at
            row.min_booking_minor = coupon.min_booking_minor
            row.max_discount_minor = coupon.max_discount_minor
            row.total_limit = coupon.total_limit
            row.per_user_limit = coupon.per_user_limit
            row.first_booking_only = coupon.first_booking_only
            row.property_ids = list(coupon.applies_to_property_ids)
        await self._session.flush()

    def pending_events(self) -> list[Any]:
        events: list[Any] = []
        for coupon, _ in self._identity.values():
            events.extend(coupon.pull_events())
        return events

    def _track(self, row: CouponModel | None) -> Coupon | None:
        if row is None:
            return None
        if row.id in self._identity:
            return self._identity[row.id][0]
        coupon = _to_domain(row)
        self._identity[row.id] = (coupon, row)
        return coupon
