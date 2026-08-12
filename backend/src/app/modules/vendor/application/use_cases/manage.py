"""Vendor registration and review."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.clock import Clock
from app.core.logging import get_logger
from app.modules.vendor.application.ports import VendorAccess, VendorRepository
from app.modules.vendor.domain import errors
from app.modules.vendor.domain.entities import Vendor
from app.shared.application.use_case import Actor

logger = get_logger(__name__)


@dataclass(slots=True)
class RegisterVendor:
    """A user applies to list properties.

    One application per user, enforced by a unique constraint rather than a
    prior read: two taps on a slow connection would both pass a check-then-act.
    """

    vendors: VendorRepository
    access: VendorAccess
    clock: Clock

    async def execute(self, data: dict[str, str], actor: Actor) -> Vendor:
        if actor.user_id is None:
            raise errors.VendorAccessDeniedError

        existing = await self.vendors.get_by_owner(actor.user_id)
        if existing is not None:
            return existing

        vendor = Vendor.register(
            owner_user_id=actor.user_id,
            legal_name=data["legal_name"],
            display_name=data.get("display_name", ""),
            contact_email=data["contact_email"],
            contact_phone=data["contact_phone"],
            gstin=data.get("gstin") or None,
            pan=data.get("pan") or None,
        )
        await self.vendors.add(vendor)
        # The vendor row alone is inert. Every vendor endpoint authorises on
        # the ``vendor_id`` and roles carried in the access token, which come
        # from the *user* row — so without this the applicant would be locked
        # out of the portal they just applied for.
        await self.access.grant(user_id=actor.user_id, vendor_id=vendor.id)
        logger.info("vendor_registered", vendor_id=str(vendor.id))
        return vendor


@dataclass(slots=True)
class ReviewVendor:
    """Approve, reject or suspend.

    All three in one use case because they are one decision with three
    outcomes, and splitting them would duplicate the lookup and the audit line.
    """

    vendors: VendorRepository
    clock: Clock

    async def approve(
        self, vendor_id: uuid.UUID, actor: Actor, commission_bps: int | None = None
    ) -> Vendor:
        vendor = await self._get(vendor_id)
        vendor.approve(by=_admin_id(actor), now=self.clock.now(), commission_bps=commission_bps)
        logger.info(
            "vendor_approved",
            vendor_id=str(vendor.id),
            by=str(actor.user_id),
            commission_bps=vendor.commission_bps,
        )
        return vendor

    async def reject(self, vendor_id: uuid.UUID, reason: str, actor: Actor) -> Vendor:
        vendor = await self._get(vendor_id)
        vendor.reject(by=_admin_id(actor), reason=reason)
        logger.info("vendor_rejected", vendor_id=str(vendor.id), by=str(actor.user_id))
        return vendor

    async def suspend(self, vendor_id: uuid.UUID, reason: str, actor: Actor) -> Vendor:
        vendor = await self._get(vendor_id)
        vendor.suspend(by=_admin_id(actor), reason=reason)
        # Warning, not info: a suspension stops payouts to a real business and
        # someone will ask who did it and why.
        logger.warning(
            "vendor_suspended",
            vendor_id=str(vendor.id),
            by=str(actor.user_id),
            reason=reason,
        )
        return vendor

    async def begin_review(self, vendor_id: uuid.UUID, actor: Actor) -> Vendor:
        vendor = await self._get(vendor_id)
        vendor.begin_review()
        return vendor

    async def _get(self, vendor_id: uuid.UUID) -> Vendor:
        vendor = await self.vendors.get(vendor_id)
        if vendor is None:
            raise errors.VendorNotFoundError
        return vendor


def _admin_id(actor: Actor) -> uuid.UUID:
    """Every decision is attributable to a person.

    A moderation action with no author is one nobody can be asked about, so an
    actor without a user id is refused rather than recorded as the system.
    """
    if actor.user_id is None:
        raise errors.VendorAccessDeniedError
    return actor.user_id
