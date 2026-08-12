"""Vendor wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.interface.api.deps import ContainerDep
from app.modules.vendor.application.use_cases.manage import RegisterVendor, ReviewVendor
from app.modules.vendor.infrastructure.queries import VendorQueries
from app.modules.vendor.infrastructure.unit_of_work import VendorUow


async def get_vendor_uow(container: ContainerDep) -> AsyncIterator[VendorUow]:
    async with container.database.write_session() as session:
        uow = VendorUow(session)
        yield uow
        await uow.flush()


VendorUowDep = Annotated[VendorUow, Depends(get_vendor_uow)]


def register_vendor_uc(container: ContainerDep, uow: VendorUowDep) -> RegisterVendor:
    return RegisterVendor(vendors=uow.vendors, access=uow.access, clock=container.clock)


def review_vendor_uc(container: ContainerDep, uow: VendorUowDep) -> ReviewVendor:
    return ReviewVendor(vendors=uow.vendors, clock=container.clock)


async def get_vendor_read_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    """Reports read from the **replica**.

    A host running a twelve-month statement should not compete with checkout
    for a connection on the primary, and replication lag of a second is
    irrelevant to a monthly total.
    """
    async with container.database.read_session() as session:
        yield session


def vendor_queries(
    session: Annotated[AsyncSession, Depends(get_vendor_read_session)],
) -> VendorQueries:
    return VendorQueries(session)


VendorQueriesDep = Annotated[VendorQueries, Depends(vendor_queries)]
