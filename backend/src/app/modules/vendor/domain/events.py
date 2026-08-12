"""Vendor domain events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, ClassVar

from app.shared.domain.events import DomainEvent

AGGREGATE = "vendor"


@dataclass(frozen=True, kw_only=True)
class VendorRegistered(DomainEvent):
    event_type: ClassVar[str] = "vendor.registered"
    aggregate_type: ClassVar[str] = AGGREGATE

    owner_user_id: uuid.UUID
    legal_name: str
    contact_email: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "vendor_id": str(self.aggregate_id),
            "owner_user_id": str(self.owner_user_id),
            "legal_name": self.legal_name,
            "contact_email": self.contact_email,
        }


@dataclass(frozen=True, kw_only=True)
class VendorApproved(DomainEvent):
    """Consumed by notifications, and by anything that gates on payouts."""

    event_type: ClassVar[str] = "vendor.approved"
    aggregate_type: ClassVar[str] = AGGREGATE

    owner_user_id: uuid.UUID
    legal_name: str
    contact_email: str
    commission_bps: int
    approved_by: uuid.UUID

    def to_payload(self) -> dict[str, Any]:
        return {
            "vendor_id": str(self.aggregate_id),
            "owner_user_id": str(self.owner_user_id),
            "legal_name": self.legal_name,
            "contact_email": self.contact_email,
            "commission_bps": self.commission_bps,
            "approved_by": str(self.approved_by),
        }


@dataclass(frozen=True, kw_only=True)
class VendorRejected(DomainEvent):
    event_type: ClassVar[str] = "vendor.rejected"
    aggregate_type: ClassVar[str] = AGGREGATE

    owner_user_id: uuid.UUID
    contact_email: str
    reason: str
    rejected_by: uuid.UUID

    def to_payload(self) -> dict[str, Any]:
        return {
            "vendor_id": str(self.aggregate_id),
            "owner_user_id": str(self.owner_user_id),
            "contact_email": self.contact_email,
            "reason": self.reason,
            "rejected_by": str(self.rejected_by),
        }


@dataclass(frozen=True, kw_only=True)
class VendorSuspended(DomainEvent):
    """Existing bookings are deliberately untouched — see `Vendor.suspend`."""

    event_type: ClassVar[str] = "vendor.suspended"
    aggregate_type: ClassVar[str] = AGGREGATE

    owner_user_id: uuid.UUID
    reason: str
    suspended_by: uuid.UUID

    def to_payload(self) -> dict[str, Any]:
        return {
            "vendor_id": str(self.aggregate_id),
            "owner_user_id": str(self.owner_user_id),
            "reason": self.reason,
            "suspended_by": str(self.suspended_by),
        }
