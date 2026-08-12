"""Coupon persistence.

The redemption table is the interesting one: it is what makes limits real.
An in-memory counter cannot survive two people redeeming the last code at the
same instant, so the guarantee lives in a unique constraint and a conditional
UPDATE — the same shape as the inventory guard in the property module.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import AuditMixin, UUIDPrimaryKeyMixin, VersionMixin


class CouponModel(Base, UUIDPrimaryKeyMixin, AuditMixin, VersionMixin):
    __tablename__ = "coupons"

    code: Mapped[str] = mapped_column(String(24), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    discount_type: Mapped[str] = mapped_column(String(10), nullable=False)
    #: Basis points for a percentage, minor units for a flat amount.
    value: Mapped[int] = mapped_column(BigInteger, nullable=False)

    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'active'"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    min_booking_minor: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    max_discount_minor: Mapped[int | None] = mapped_column(BigInteger)
    total_limit: Mapped[int | None] = mapped_column(Integer)
    per_user_limit: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    first_booking_only: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"))
    #: Empty means every property. An array rather than a join table: the list
    #: is short, read on every validation, and never queried from the other
    #: side.
    property_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), nullable=False, server_default=text("'{}'")
    )

    #: Maintained by the conditional UPDATE in the repository, which is what
    #: makes `total_limit` enforceable under concurrency.
    redeemed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    __mapper_args__ = {"version_id_col": VersionMixin.version}  # noqa: RUF012

    __table_args__ = (
        UniqueConstraint("code", name="uq_coupons_code"),
        CheckConstraint("discount_type IN ('percent','flat')", name="type_valid"),
        CheckConstraint("status IN ('active','inactive','expired')", name="status_valid"),
        CheckConstraint("value > 0", name="value_positive"),
        CheckConstraint("ends_at > starts_at", name="window_ordered"),
        CheckConstraint("per_user_limit >= 1", name="per_user_limit_positive"),
        # A percentage over 100 would pay the guest to book.
        CheckConstraint(
            "discount_type <> 'percent' OR value <= 10000", name="percent_within_range"
        ),
        # An uncapped percentage is the most expensive mistake available here.
        CheckConstraint(
            "discount_type <> 'percent' OR max_discount_minor IS NOT NULL",
            name="percent_needs_cap",
        ),
        # The counter can never exceed the limit, whatever the application does.
        CheckConstraint(
            "total_limit IS NULL OR redeemed_count <= total_limit",
            name="redemptions_within_limit",
        ),
        Index("ix_coupons_live", "ends_at", postgresql_where=text("status = 'active'")),
    )


class CouponRedemptionModel(Base, UUIDPrimaryKeyMixin):
    """One row per discount actually granted.

    Append-only, and the unique constraints are the enforcement: `(coupon_id,
    booking_id)` stops a retried request discounting twice, and the per-user
    limit is counted from here rather than trusted from a cached number.
    """

    __tablename__ = "coupon_redemptions"

    coupon_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("coupons.id", ondelete="RESTRICT"), nullable=False
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    discount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    #: Set if the booking is later cancelled, so a refunded redemption can be
    #: returned to the pool rather than being lost.
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        # A retried booking request must not discount twice.
        UniqueConstraint("coupon_id", "booking_id", name="uq_redemption_booking"),
        CheckConstraint("discount_minor >= 0", name="discount_non_negative"),
        Index("ix_redemptions_user", "coupon_id", "user_id"),
        Index("ix_redemptions_reporting", "redeemed_at", "coupon_id"),
    )
