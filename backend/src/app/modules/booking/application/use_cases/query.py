"""Reading bookings: history, detail, vendor arrivals, invoice."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.types.pagination import Cursor
from app.modules.booking.application.dto import (
    BookingListView,
    BookingView,
    InvoiceView,
)
from app.modules.booking.application.ports import BookingRepository
from app.modules.booking.application.views import to_booking_view
from app.modules.booking.domain import errors
from app.modules.booking.domain.entities import Booking
from app.modules.booking.domain.invoice import Invoice, build_lines, financial_year
from app.modules.booking.domain.value_objects import BookingReference, BookingStatus
from app.modules.property.public import PropertyCatalog
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)


@dataclass(slots=True)
class GetBookingUseCase:
    bookings: BookingRepository
    catalog: PropertyCatalog
    clock: Clock

    async def execute(self, identifier: str, actor: Actor) -> BookingView:
        """Look up by id **or** by reference.

        Support agents work from the reference a guest reads out over the
        phone; clients hold the id. Both resolve here rather than making the
        caller know which one they have.
        """
        booking = await self._resolve(identifier)
        if booking is None:
            raise EntityNotFoundError("Booking", identifier)

        is_staff = actor.has_role("admin", "superadmin", "support")
        # Raises BookingAccessDeniedError, which the interface maps to 404 —
        # a 403 would confirm the reference exists and turn this endpoint into
        # an oracle for guessing them.
        booking.assert_visible_to(
            user_id=actor.user_id, vendor_id=actor.vendor_id, is_staff=is_staff
        )

        now = self.clock.now()
        confirmed = booking.status in (
            BookingStatus.CONFIRMED,
            BookingStatus.IN_STAY,
            BookingStatus.COMPLETED,
        )

        address = None
        if confirmed:
            # The exact address is released only once the guest has committed.
            snapshot = await self.catalog.snapshot(booking.property_id)
            address = snapshot.full_address if snapshot else None

        preview = None
        if booking.status.is_cancellable_by_guest and actor.user_id == booking.guest_id:
            now_local = now.astimezone(ZoneInfo(booking.stay.timezone)).replace(tzinfo=None)
            preview = booking.preview_refund(now_local).to_payload()

        return to_booking_view(
            booking,
            now=now,
            include_address=confirmed,
            property_address=address,
            refund_preview=preview,
        )

    async def _resolve(self, identifier: str) -> Booking | None:
        try:
            return await self.bookings.get(uuid.UUID(identifier))
        except ValueError:
            pass
        try:
            return await self.bookings.get_by_reference(BookingReference(identifier.upper()))
        except ValueError:
            return None


@dataclass(slots=True)
class ListGuestBookingsUseCase:
    """A guest's booking history.

    Cursor-paged: a frequent traveller's history is unbounded, and a new
    booking arriving mid-scroll would shift every offset page below it.
    """

    bookings: BookingRepository
    clock: Clock

    async def execute(
        self, args: tuple[str | None, bool, int, str | None], actor: Actor
    ) -> BookingListView:
        status_filter, upcoming_only, limit, raw_cursor = args
        if actor.user_id is None:  # pragma: no cover — route requires auth
            raise errors.BookingAccessDeniedError

        statuses = [BookingStatus(status_filter)] if status_filter else None
        cursor = _decode_cursor(raw_cursor)

        items, has_more = await self.bookings.list_for_guest(
            actor.user_id,
            statuses=statuses,
            upcoming_only=upcoming_only,
            limit=limit,
            cursor=cursor,
        )

        now = self.clock.now()
        views = [to_booking_view(b, now=now) for b in items]
        next_cursor = (
            Cursor((items[-1].created_at.isoformat(), str(items[-1].id))).encode()
            if has_more and items and items[-1].created_at
            else None
        )
        return BookingListView(items=views, next_cursor=next_cursor)


@dataclass(slots=True)
class ListVendorBookingsUseCase:
    """The vendor's arrivals and departures view.

    Offset-paged, unlike guest history: a vendor filters to a date range and
    wants page numbers, and the set is bounded by their own properties.
    """

    bookings: BookingRepository
    clock: Clock

    async def execute(
        self,
        args: tuple[uuid.UUID | None, str | None, date | None, date | None, int, int],
        actor: Actor,
    ) -> BookingListView:
        property_id, status_filter, from_date, to_date, page, size = args
        if actor.vendor_id is None:
            return BookingListView(items=[], total=0)

        items, total = await self.bookings.list_for_vendor(
            actor.vendor_id,
            property_id=property_id,
            statuses=[BookingStatus(status_filter)] if status_filter else None,
            from_date=from_date,
            to_date=to_date,
            limit=size,
            offset=(page - 1) * size,
        )
        now = self.clock.now()
        # Vendors get the guest's contact details — they need to reach an
        # arriving guest — but only for bookings at their own properties, which
        # the repository query already scopes.
        return BookingListView(items=[to_booking_view(b, now=now) for b in items], total=total)


@dataclass(slots=True)
class GetInvoiceUseCase:
    """Render the tax invoice.

    Built from the booking on demand rather than stored as a second copy of the
    numbers. The booking's charges are the single source; a stored render would
    drift the moment anything about formatting or tax presentation changed, and
    two versions of a tax document is the one thing an auditor cannot accept.

    The *number* is stored, because it must be stable and gapless.
    """

    bookings: BookingRepository
    catalog: PropertyCatalog
    clock: Clock

    async def execute(self, booking_id: uuid.UUID, actor: Actor) -> InvoiceView:
        booking = await self.bookings.get(booking_id)
        if booking is None:
            raise EntityNotFoundError("Booking", booking_id)
        booking.assert_visible_to(
            user_id=actor.user_id,
            vendor_id=actor.vendor_id,
            is_staff=actor.has_role("admin", "superadmin", "support"),
        )

        if booking.invoice_number is None or booking.invoice_issued_at is None:
            raise errors.InvoiceNotAvailableError(booking.status.value)

        snapshot = await self.catalog.snapshot(booking.property_id)
        charges = booking.charges

        lines = build_lines(
            room_type_name=booking.room_type_name,
            nights=booking.stay.nights,
            rooms=booking.rooms,
            accommodation=charges.accommodation,
            extra_guest=charges.extra_guest,
            cleaning_fee=charges.cleaning_fee,
            tax_rate=_effective_tax_rate(booking),
        )

        invoice = Invoice(
            number=booking.invoice_number,
            issued_at=booking.invoice_issued_at,
            financial_year=financial_year(booking.invoice_issued_at.date()),
            supplier_name=booking.property_name,
            supplier_address=snapshot.full_address if snapshot else "",
            supplier_gstin=None,  # populated once vendor KYC lands
            guest_name=booking.guest.full_name,
            guest_email=booking.guest.email,
            guest_address=None,
            booking_reference=str(booking.reference),
            property_name=booking.property_name,
            check_in=booking.stay.check_in_date,
            check_out=booking.stay.check_out_date,
            nights=booking.stay.nights,
            rooms=booking.rooms,
            lines=lines,
            subtotal=charges.accommodation + charges.extra_guest + charges.cleaning_fee,
            tax_total=charges.tax,
            total=charges.total,
            place_of_supply=snapshot.city if snapshot else "",
            currency=charges.currency,
        )

        return InvoiceView(
            number=invoice.number,
            issued_at=invoice.issued_at,
            financial_year=invoice.financial_year,
            booking_reference=invoice.booking_reference,
            supplier_name=invoice.supplier_name,
            supplier_address=invoice.supplier_address,
            supplier_gstin=invoice.supplier_gstin,
            guest_name=invoice.guest_name,
            guest_email=invoice.guest_email,
            property_name=invoice.property_name,
            check_in=invoice.check_in,
            check_out=invoice.check_out,
            nights=invoice.nights,
            rooms=invoice.rooms,
            lines=[
                {
                    "description": line.description,
                    "hsn_code": line.hsn_code,
                    "quantity": line.quantity,
                    "unit_amount_minor": line.unit_amount.amount_minor,
                    "amount_minor": line.amount.amount_minor,
                    "tax_rate": str(line.tax_rate),
                }
                for line in invoice.lines
            ],
            subtotal_minor=invoice.subtotal.amount_minor,
            cgst_minor=invoice.cgst.amount_minor,
            sgst_minor=invoice.sgst.amount_minor,
            igst_minor=invoice.igst.amount_minor,
            tax_total_minor=invoice.tax_total.amount_minor,
            total_minor=invoice.total.amount_minor,
            total_in_words=invoice.total_in_words(),
            place_of_supply=invoice.place_of_supply,
            currency=invoice.currency,
        )


def _effective_tax_rate(booking: Booking) -> Decimal:
    """Derive the rate actually charged, rather than reading today's config.

    The vendor may have changed their tax rate since; the invoice must show
    what the guest was charged.
    """
    base = booking.charges.taxable_base
    if base.is_zero:
        return Decimal("0")
    return (Decimal(booking.charges.tax.amount_minor) / Decimal(base.amount_minor)).quantize(
        Decimal("0.001")
    )


def _decode_cursor(raw: str | None) -> tuple[datetime, uuid.UUID] | None:
    if not raw:
        return None
    values = Cursor.decode(raw).values
    return (datetime.fromisoformat(str(values[0])), uuid.UUID(str(values[1])))
