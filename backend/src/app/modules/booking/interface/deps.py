"""Booking module wiring.

Note that the property module's adapters are constructed here, from the
booking module's own session. That is what keeps them in one transaction: the
booking row and the inventory it holds are written together or not at all.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from app.interface.api.deps import ContainerDep
from app.modules.booking.application.use_cases.cancel import (
    CancelBookingUseCase,
    PreviewRefundUseCase,
)
from app.modules.booking.application.use_cases.create import CreateBookingUseCase
from app.modules.booking.application.use_cases.lifecycle import (
    ApproveBookingUseCase,
    CompleteStaysUseCase,
    ConfirmBookingUseCase,
    ExpireHoldsUseCase,
    FlatCommission,
    RejectBookingUseCase,
    StartStaysUseCase,
)
from app.modules.booking.application.use_cases.query import (
    GetBookingUseCase,
    GetInvoiceUseCase,
    ListGuestBookingsUseCase,
    ListVendorBookingsUseCase,
)
from app.modules.booking.infrastructure.unit_of_work import BookingUow


async def get_booking_uow(container: ContainerDep) -> AsyncIterator[BookingUow]:
    """Always the **primary**, never a replica.

    Availability read from a replica is stale by the length of replication lag,
    and a booking taken against stale inventory is an overbooking.
    """
    async with container.database.write_session() as session:
        uow = BookingUow(session)
        yield uow
        await uow.flush()


BookingUowDep = Annotated[BookingUow, Depends(get_booking_uow)]


# ══════════════════════════════════════════════════════════════════════════
# Use-case providers
# ══════════════════════════════════════════════════════════════════════════


def create_booking_uc(container: ContainerDep, uow: BookingUowDep) -> CreateBookingUseCase:
    return CreateBookingUseCase(
        bookings=uow.bookings,
        catalog=uow.catalog,
        inventory=uow.inventory,
        clock=container.clock,
    )


def confirm_booking_uc(container: ContainerDep, uow: BookingUowDep) -> ConfirmBookingUseCase:
    return ConfirmBookingUseCase(
        bookings=uow.bookings,
        invoice_numbers=uow.invoice_numbers,
        inventory=uow.inventory,
        clock=container.clock,
    )


def cancel_booking_uc(container: ContainerDep, uow: BookingUowDep) -> CancelBookingUseCase:
    return CancelBookingUseCase(
        bookings=uow.bookings, inventory=uow.inventory, clock=container.clock
    )


def preview_refund_uc(container: ContainerDep, uow: BookingUowDep) -> PreviewRefundUseCase:
    return PreviewRefundUseCase(bookings=uow.bookings, clock=container.clock)


def approve_booking_uc(container: ContainerDep, uow: BookingUowDep) -> ApproveBookingUseCase:
    return ApproveBookingUseCase(bookings=uow.bookings, clock=container.clock)


def reject_booking_uc(container: ContainerDep, uow: BookingUowDep) -> RejectBookingUseCase:
    return RejectBookingUseCase(
        bookings=uow.bookings, inventory=uow.inventory, clock=container.clock
    )


def get_booking_uc(container: ContainerDep, uow: BookingUowDep) -> GetBookingUseCase:
    return GetBookingUseCase(bookings=uow.bookings, catalog=uow.catalog, clock=container.clock)


def list_guest_bookings_uc(container: ContainerDep, uow: BookingUowDep) -> ListGuestBookingsUseCase:
    return ListGuestBookingsUseCase(bookings=uow.bookings, clock=container.clock)


def list_vendor_bookings_uc(
    container: ContainerDep, uow: BookingUowDep
) -> ListVendorBookingsUseCase:
    return ListVendorBookingsUseCase(bookings=uow.bookings, clock=container.clock)


def get_invoice_uc(container: ContainerDep, uow: BookingUowDep) -> GetInvoiceUseCase:
    return GetInvoiceUseCase(bookings=uow.bookings, catalog=uow.catalog, clock=container.clock)


def expire_holds_uc(container: ContainerDep, uow: BookingUowDep) -> ExpireHoldsUseCase:
    return ExpireHoldsUseCase(bookings=uow.bookings, inventory=uow.inventory, clock=container.clock)


def start_stays_uc(container: ContainerDep, uow: BookingUowDep) -> StartStaysUseCase:
    return StartStaysUseCase(bookings=uow.bookings, clock=container.clock)


def complete_stays_uc(container: ContainerDep, uow: BookingUowDep) -> CompleteStaysUseCase:
    return CompleteStaysUseCase(
        bookings=uow.bookings,
        inventory=uow.inventory,
        commission=FlatCommission(),
        clock=container.clock,
    )
