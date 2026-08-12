"""Vendor persistence.

**No full bank account number and no document images.** Only a last-4, an IFSC
and the tax identifiers the platform is legally required to hold. Account
numbers go to the payout provider directly; KYC documents live in object
storage behind signed URLs. A table that holds either becomes the most
attractive thing in the database.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionMixin


class VendorModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionMixin):
    __tablename__ = "vendors"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        # RESTRICT: a vendor with payouts and invoices behind it must not
        # vanish because someone deleted the user who signed up.
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    legal_name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'pending'")
    )

    gstin: Mapped[str | None] = mapped_column(String(15))
    pan: Mapped[str | None] = mapped_column(String(10))
    #: Last four digits only. See the module docstring.
    bank_account_last4: Mapped[str | None] = mapped_column(String(4))
    bank_ifsc: Mapped[str | None] = mapped_column(String(11))

    #: Basis points. An integer, because a float commission on a large booking
    #: rounds differently on two machines.
    commission_bps: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1500")
    )

    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    suspension_reason: Mapped[str | None] = mapped_column(Text)

    __mapper_args__ = {"version_id_col": VersionMixin.version}  # noqa: RUF012

    __table_args__ = (
        # One vendor account per user: two would make "which one gets paid?"
        # ambiguous at payout time.
        UniqueConstraint("owner_user_id", name="uq_vendors_owner"),
        UniqueConstraint("gstin", name="uq_vendors_gstin"),
        UniqueConstraint("pan", name="uq_vendors_pan"),
        CheckConstraint(
            "status IN ('pending','under_review','approved','rejected','suspended')",
            name="status_valid",
        ),
        CheckConstraint("commission_bps BETWEEN 0 AND 3000", name="commission_within_range"),
        # Approved means a human decided; the decision and its author are not
        # optional.
        CheckConstraint(
            "status <> 'approved' OR (approved_at IS NOT NULL AND pan IS NOT NULL)",
            name="approved_needs_evidence",
        ),
        # The review queue, which is the only query an admin runs all day.
        Index(
            "ix_vendors_review_queue",
            "created_at",
            postgresql_where=text("status IN ('pending','under_review')"),
        ),
        Index("ix_vendors_status", "status", "created_at"),
    )
