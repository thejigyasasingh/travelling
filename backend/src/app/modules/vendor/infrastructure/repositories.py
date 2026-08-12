"""Vendor persistence adapter."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.vendor.domain.entities import Vendor
from app.modules.vendor.domain.value_objects import VendorStatus
from app.modules.vendor.infrastructure.models import VendorModel


def _to_domain(row: VendorModel) -> Vendor:
    return Vendor(
        entity_id=row.id,
        owner_user_id=row.owner_user_id,
        legal_name=row.legal_name,
        display_name=row.display_name,
        contact_email=row.contact_email,
        contact_phone=row.contact_phone,
        status=VendorStatus(row.status),
        gstin=row.gstin,
        pan=row.pan,
        bank_account_last4=row.bank_account_last4,
        bank_ifsc=row.bank_ifsc,
        commission_bps=row.commission_bps,
        approved_at=row.approved_at,
        approved_by=row.approved_by,
        rejection_reason=row.rejection_reason,
        suspension_reason=row.suspension_reason,
        version=row.version,
    )


def _apply(vendor: Vendor, row: VendorModel) -> None:
    row.legal_name = vendor.legal_name
    row.display_name = vendor.display_name
    row.contact_email = vendor.contact_email
    row.contact_phone = vendor.contact_phone
    row.status = vendor.status.value
    row.gstin = vendor.gstin
    row.pan = vendor.pan
    row.bank_account_last4 = vendor.bank_account_last4
    row.bank_ifsc = vendor.bank_ifsc
    row.commission_bps = vendor.commission_bps
    row.approved_at = vendor.approved_at
    row.approved_by = vendor.approved_by
    row.rejection_reason = vendor.rejection_reason
    row.suspension_reason = vendor.suspension_reason


class SqlVendorRepository:
    """Identity-mapped, like the other repositories: one aggregate instance per
    id per transaction, so two reads cannot diverge and there is no `save()` to
    forget."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._identity: dict[uuid.UUID, tuple[Vendor, VendorModel]] = {}

    async def get(self, vendor_id: uuid.UUID) -> Vendor | None:
        if vendor_id in self._identity:
            return self._identity[vendor_id][0]
        return self._track(await self._session.get(VendorModel, vendor_id))

    async def get_by_owner(self, user_id: uuid.UUID) -> Vendor | None:
        row = (
            await self._session.execute(
                select(VendorModel).where(VendorModel.owner_user_id == user_id)
            )
        ).scalar_one_or_none()
        return self._track(row)

    async def add(self, vendor: Vendor) -> None:
        row = VendorModel(
            id=vendor.id,
            owner_user_id=vendor.owner_user_id,
            legal_name=vendor.legal_name,
            display_name=vendor.display_name,
            contact_email=vendor.contact_email,
            contact_phone=vendor.contact_phone,
            status=vendor.status.value,
            gstin=vendor.gstin,
            pan=vendor.pan,
            commission_bps=vendor.commission_bps,
        )
        self._session.add(row)
        self._identity[vendor.id] = (vendor, row)

    async def list_for_admin(
        self,
        *,
        status: str | None = None,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Vendor], int]:
        """Offset paging, unlike the guest-facing lists.

        This is a bounded internal set that an admin pages through by number
        and sorts by column; cursor paging would make "page 4" unexpressible
        and is optimising for a scale this table will not reach.
        """
        stmt = select(VendorModel)
        count_stmt = select(func.count()).select_from(VendorModel)

        if status:
            stmt = stmt.where(VendorModel.status == status)
            count_stmt = count_stmt.where(VendorModel.status == status)
        if query:
            pattern = f"%{query.lower()}%"
            condition = func.lower(VendorModel.legal_name).like(pattern) | func.lower(
                VendorModel.contact_email
            ).like(pattern)
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        stmt = stmt.order_by(VendorModel.created_at.desc()).limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        total = int((await self._session.execute(count_stmt)).scalar() or 0)
        return [v for v in (self._track(r) for r in rows) if v is not None], total

    async def flush(self) -> None:
        for vendor, row in self._identity.values():
            _apply(vendor, row)
        await self._session.flush()

    def pending_events(self) -> list[Any]:
        events: list[Any] = []
        for vendor, _ in self._identity.values():
            events.extend(vendor.pull_events())
        return events

    def _track(self, row: VendorModel | None) -> Vendor | None:
        if row is None:
            return None
        if row.id in self._identity:
            return self._identity[row.id][0]
        vendor = _to_domain(row)
        self._identity[row.id] = (vendor, row)
        return vendor
