"""Booking persistence and the invoice number generator."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.core.types.money import Money
from app.modules.booking.domain.entities import Booking, RefundRecord
from app.modules.booking.domain.invoice import financial_year
from app.modules.booking.domain.refund_policy import ChargeBreakdown, PolicyName
from app.modules.booking.domain.value_objects import (
    BookingReference,
    BookingStatus,
    CancelledBy,
    GuestDetails,
    HoldWindow,
    RefundStatus,
    StayWindow,
)
from app.modules.booking.infrastructure.models import (
    BookingModel,
    InvoiceSequenceModel,
    RefundModel,
)

logger = get_logger(__name__)


def _parse_time(value: str, default: time) -> time:
    try:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))
    except (ValueError, AttributeError):  # pragma: no cover
        return default


def _to_domain(row: BookingModel) -> Booking:
    currency = row.currency
    refund = None
    if row.refund is not None:
        refund = RefundRecord(
            booking_id=row.id,
            amount=Money(row.refund.amount_minor, row.refund.currency),
            reason=row.refund.reason,
            status=RefundStatus(row.refund.status),
            gateway_refund_id=row.refund.gateway_refund_id,
            attempts=row.refund.attempts,
            last_error=row.refund.last_error,
            requested_at=row.refund.requested_at,
            completed_at=row.refund.completed_at,
        )

    return Booking(
        entity_id=row.id,
        reference=BookingReference(row.reference),
        guest_id=row.guest_id,
        guest=GuestDetails(
            full_name=row.guest_name,
            email=row.guest_email,
            phone=row.guest_phone,
            special_requests=row.special_requests,
        ),
        property_id=row.property_id,
        property_name=row.property_name,
        vendor_id=row.vendor_id,
        room_type_id=row.room_type_id,
        room_type_name=row.room_type_name,
        stay=StayWindow(
            check_in_date=row.check_in,
            check_out_date=row.check_out,
            check_in_time=_parse_time(row.check_in_time, time(14, 0)),
            check_out_time=_parse_time(row.check_out_time, time(11, 0)),
            timezone=row.timezone,
        ),
        charges=ChargeBreakdown(
            accommodation=Money(row.accommodation_minor, currency),
            extra_guest=Money(row.extra_guest_minor, currency),
            cleaning_fee=Money(row.cleaning_fee_minor, currency),
            tax=Money(row.tax_minor, currency),
            platform_fee=Money(row.platform_fee_minor, currency),
        ),
        cancellation_policy=PolicyName(row.cancellation_policy),
        adults=row.adults,
        children=row.children,
        infants=row.infants,
        rooms=row.rooms,
        status=BookingStatus(row.status),
        hold=HoldWindow(row.hold_expires_at) if row.hold_expires_at else None,
        nightly_rates=list(row.nightly_rates or []),
        payment_id=row.payment_id,
        invoice_number=row.invoice_number,
        invoice_issued_at=row.invoice_issued_at,
        refund=refund,
        confirmed_at=row.confirmed_at,
        cancelled_at=row.cancelled_at,
        cancelled_by=CancelledBy(row.cancelled_by) if row.cancelled_by else None,
        cancellation_reason=row.cancellation_reason,
        source=row.source,
        created_at=row.created_at,
        version=row.version,
    )


def _to_model(booking: Booking) -> BookingModel:
    charges = booking.charges
    row = BookingModel(
        id=booking.id,
        reference=str(booking.reference),
        status=booking.status.value,
        guest_id=booking.guest_id,
        property_id=booking.property_id,
        vendor_id=booking.vendor_id,
        room_type_id=booking.room_type_id,
        property_name=booking.property_name,
        room_type_name=booking.room_type_name,
        cancellation_policy=booking.cancellation_policy.value,
        check_in=booking.stay.check_in_date,
        check_out=booking.stay.check_out_date,
        check_in_time=booking.stay.check_in_time.strftime("%H:%M"),
        check_out_time=booking.stay.check_out_time.strftime("%H:%M"),
        timezone=booking.stay.timezone,
        stay_range=func.daterange(booking.stay.check_in_date, booking.stay.check_out_date, "[)"),
        adults=booking.adults,
        children=booking.children,
        infants=booking.infants,
        rooms=booking.rooms,
        guest_name=booking.guest.full_name,
        guest_email=booking.guest.email,
        guest_phone=booking.guest.phone,
        special_requests=booking.guest.special_requests,
        accommodation_minor=charges.accommodation.amount_minor,
        extra_guest_minor=charges.extra_guest.amount_minor,
        cleaning_fee_minor=charges.cleaning_fee.amount_minor,
        tax_minor=charges.tax.amount_minor,
        platform_fee_minor=charges.platform_fee.amount_minor,
        total_minor=charges.total.amount_minor,
        currency=charges.currency,
        nightly_rates=booking.nightly_rates,
        hold_expires_at=booking.hold.expires_at if booking.hold else None,
        confirmed_at=booking.confirmed_at,
        cancelled_at=booking.cancelled_at,
        cancelled_by=booking.cancelled_by.value if booking.cancelled_by else None,
        cancellation_reason=booking.cancellation_reason,
        payment_id=booking.payment_id,
        invoice_number=booking.invoice_number,
        invoice_issued_at=booking.invoice_issued_at,
        source=booking.source,
    )
    if booking.refund is not None:
        row.refund = _refund_to_model(booking.refund, booking.id)
    return row


def _refund_to_model(refund: RefundRecord, booking_id: uuid.UUID) -> RefundModel:
    return RefundModel(
        booking_id=booking_id,
        status=refund.status.value,
        amount_minor=refund.amount.amount_minor,
        currency=refund.amount.currency,
        reason=refund.reason,
        gateway_refund_id=refund.gateway_refund_id,
        attempts=refund.attempts,
        last_error=refund.last_error,
        requested_at=refund.requested_at or utcnow(),
        completed_at=refund.completed_at,
    )


def _apply(booking: Booking, row: BookingModel) -> None:
    """Write mutable state back.

    The money columns are deliberately absent: charges are fixed at booking
    time and must never be rewritten. A repriced booking is a different
    booking, and silently updating the amount would break every reconciliation
    that already counted the original.
    """
    row.status = booking.status.value
    row.hold_expires_at = booking.hold.expires_at if booking.hold else None
    row.confirmed_at = booking.confirmed_at
    row.cancelled_at = booking.cancelled_at
    row.cancelled_by = booking.cancelled_by.value if booking.cancelled_by else None
    row.cancellation_reason = booking.cancellation_reason
    row.payment_id = booking.payment_id
    row.invoice_number = booking.invoice_number
    row.invoice_issued_at = booking.invoice_issued_at
    row.guest_name = booking.guest.full_name
    row.guest_phone = booking.guest.phone
    row.special_requests = booking.guest.special_requests

    if booking.refund is not None:
        if row.refund is None:
            row.refund = _refund_to_model(booking.refund, booking.id)
        else:
            row.refund.status = booking.refund.status.value
            row.refund.gateway_refund_id = booking.refund.gateway_refund_id
            row.refund.attempts = booking.refund.attempts
            row.refund.last_error = booking.refund.last_error
            row.refund.completed_at = booking.refund.completed_at


class SqlBookingRepository:
    """Implements
    :class:`app.modules.booking.application.ports.BookingRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._identity: dict[uuid.UUID, tuple[Booking, BookingModel]] = {}

    # ── reads ─────────────────────────────────────────────────────────────

    async def get(self, booking_id: uuid.UUID) -> Booking | None:
        if booking_id in self._identity:
            return self._identity[booking_id][0]
        row = await self._session.get(BookingModel, booking_id)
        return self._track(row)

    async def get_by_reference(self, reference: BookingReference) -> Booking | None:
        row = (
            await self._session.execute(
                select(BookingModel).where(BookingModel.reference == str(reference))
            )
        ).scalar_one_or_none()
        return self._track(row)

    async def add(self, booking: Booking) -> None:
        row = _to_model(booking)
        self._session.add(row)
        self._identity[booking.id] = (booking, row)

    async def list_for_guest(
        self,
        guest_id: uuid.UUID,
        *,
        statuses: Sequence[BookingStatus] | None = None,
        upcoming_only: bool = False,
        limit: int = 20,
        cursor: tuple[datetime, uuid.UUID] | None = None,
    ) -> tuple[list[Booking], bool]:
        stmt: Select[Any] = select(BookingModel).where(BookingModel.guest_id == guest_id)
        stmt = self._apply_status_filter(stmt, statuses)

        if upcoming_only:
            stmt = stmt.where(
                BookingModel.check_out >= func.current_date(),
                BookingModel.status.in_(["confirmed", "pending_payment", "in_stay"]),
            )

        if cursor is not None:
            # Row-value comparison, so it rides the (guest_id, created_at DESC)
            # index instead of degenerating into a filter.
            created_at, row_id = cursor
            stmt = stmt.where(
                text("(bookings.created_at, bookings.id) < (:c_at, :c_id)").bindparams(
                    c_at=created_at, c_id=row_id
                )
            )

        stmt = stmt.order_by(BookingModel.created_at.desc(), BookingModel.id.desc()).limit(
            limit + 1  # over-fetch to detect a next page without a COUNT
        )
        rows = (await self._session.execute(stmt)).scalars().all()

        has_more = len(rows) > limit
        return [_to_domain(r) for r in rows[:limit]], has_more

    async def list_for_vendor(
        self,
        vendor_id: uuid.UUID,
        *,
        property_id: uuid.UUID | None = None,
        statuses: Sequence[BookingStatus] | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Booking], int]:
        conditions = [BookingModel.vendor_id == vendor_id]
        if property_id is not None:
            conditions.append(BookingModel.property_id == property_id)
        if from_date is not None:
            conditions.append(BookingModel.check_out > from_date)
        if to_date is not None:
            conditions.append(BookingModel.check_in < to_date)

        base = select(BookingModel).where(*conditions)
        base = self._apply_status_filter(base, statuses)

        total = (
            await self._session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar() or 0

        rows = (
            (
                await self._session.execute(
                    base.order_by(BookingModel.check_in).limit(limit).offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return [_to_domain(r) for r in rows], int(total)

    async def find_expired_holds(self, *, now: datetime, limit: int = 200) -> list[Booking]:
        """Claim a batch of lapsed holds.

        ``FOR UPDATE SKIP LOCKED`` is what lets several expiry workers run at
        once: each takes rows nobody else has locked and skips the rest, so a
        hold is never released twice and the job scales by adding workers.
        """
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.status.in_(["pending_payment", "pending_approval"]),
                BookingModel.hold_expires_at.isnot(None),
                BookingModel.hold_expires_at <= now,
            )
            .order_by(BookingModel.hold_expires_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._track(r) for r in rows if r is not None]  # type: ignore[misc]

    async def find_due_for_check_in(self, *, today: date, limit: int = 500) -> list[Booking]:
        stmt = (
            select(BookingModel)
            .where(BookingModel.status == "confirmed", BookingModel.check_in <= today)
            .order_by(BookingModel.check_in)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._track(r) for r in rows if r is not None]  # type: ignore[misc]

    async def find_due_for_completion(self, *, today: date, limit: int = 500) -> list[Booking]:
        stmt = (
            select(BookingModel)
            .where(
                BookingModel.status.in_(["in_stay", "confirmed"]),
                BookingModel.check_out <= today,
            )
            .order_by(BookingModel.check_out)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._track(r) for r in rows if r is not None]  # type: ignore[misc]

    async def has_active_booking(
        self, *, guest_id: uuid.UUID, room_type_id: uuid.UUID, check_in: date
    ) -> bool:
        stmt = (
            select(BookingModel.id)
            .where(
                BookingModel.guest_id == guest_id,
                BookingModel.room_type_id == room_type_id,
                BookingModel.check_in == check_in,
                BookingModel.status.in_(
                    ["pending_payment", "pending_approval", "confirmed", "in_stay"]
                ),
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).first() is not None

    # ── unit of work ──────────────────────────────────────────────────────

    async def flush(self) -> None:
        for booking, row in self._identity.values():
            _apply(booking, row)
        await self._session.flush()

    def pending_events(self) -> list[Any]:
        events: list[Any] = []
        for booking, _ in self._identity.values():
            events.extend(booking.pull_events())
        return events

    @staticmethod
    def _apply_status_filter(
        stmt: Select[Any], statuses: Sequence[BookingStatus] | None
    ) -> Select[Any]:
        if statuses:
            return stmt.where(BookingModel.status.in_([s.value for s in statuses]))
        return stmt

    def _track(self, row: BookingModel | None) -> Booking | None:
        if row is None:
            return None
        if row.id in self._identity:
            return self._identity[row.id][0]
        booking = _to_domain(row)
        self._identity[row.id] = (booking, row)
        return booking


class SqlInvoiceNumberGenerator:
    """Gapless sequential invoice numbers.

    ``SELECT … FOR UPDATE`` on the counter row, incremented inside the caller's
    transaction. If the transaction rolls back so does the increment, which is
    exactly what a Postgres ``SEQUENCE`` cannot do — sequences are
    non-transactional by design, and every rollback would leave a gap an
    auditor has to be told about.

    The cost is that invoice creation serialises on one row per financial year.
    That is acceptable: it happens on booking confirmation rather than on
    search, and the lock is held for microseconds. At a volume where it
    genuinely contends, the answer is per-vendor series — the ``series`` column
    is already there for it.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_number(self, *, issued_on: date, series: str = "INV") -> str:
        fy = financial_year(issued_on)

        # Create the counter if this is the first invoice of the year. DO
        # NOTHING rather than DO UPDATE, so two concurrent first-invoices do
        # not both claim number 1.
        await self._session.execute(
            text(
                "INSERT INTO invoice_sequences (financial_year, series, last_number) "
                "VALUES (:fy, :series, 0) ON CONFLICT DO NOTHING"
            ),
            {"fy": fy, "series": series},
        )

        row = (
            await self._session.execute(
                select(InvoiceSequenceModel)
                .where(
                    InvoiceSequenceModel.financial_year == fy,
                    InvoiceSequenceModel.series == series,
                )
                .with_for_update()
            )
        ).scalar_one()

        row.last_number += 1
        row.updated_at = utcnow()

        # RW/INV/2026-27/000042 — the series and year are part of the number
        # itself, so an invoice is identifiable from the document alone.
        return f"RW/{series}/{fy}/{row.last_number:06d}"
