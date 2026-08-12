"""Ports for the booking module."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from typing import Protocol

from app.core.types.money import Money
from app.modules.booking.domain.entities import Booking
from app.modules.booking.domain.value_objects import BookingReference, BookingStatus


class BookingRepository(Protocol):
    async def get(self, booking_id: uuid.UUID) -> Booking | None: ...

    async def get_by_reference(self, reference: BookingReference) -> Booking | None:
        """Support looks bookings up by the reference a guest reads out."""
        ...

    async def add(self, booking: Booking) -> None: ...

    async def list_for_guest(
        self,
        guest_id: uuid.UUID,
        *,
        statuses: Sequence[BookingStatus] | None = None,
        upcoming_only: bool = False,
        limit: int = 20,
        cursor: tuple[datetime, uuid.UUID] | None = None,
    ) -> tuple[list[Booking], bool]:
        """Booking history, newest first. Returns ``(page, has_more)``.

        Cursor-paged rather than offset-paged: a frequent traveller's history
        is unbounded, and a new booking arriving mid-scroll would shift every
        subsequent offset page.
        """
        ...

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
    ) -> tuple[list[Booking], int]: ...

    async def find_expired_holds(self, *, now: datetime, limit: int = 200) -> list[Booking]:
        """Claims a batch of lapsed holds with ``FOR UPDATE SKIP LOCKED``, so
        several expiry workers can run without contending or double-releasing.
        """
        ...

    async def find_due_for_completion(self, *, today: date, limit: int = 500) -> list[Booking]: ...

    async def find_due_for_check_in(self, *, today: date, limit: int = 500) -> list[Booking]: ...

    async def has_active_booking(
        self, *, guest_id: uuid.UUID, room_type_id: uuid.UUID, check_in: date
    ) -> bool:
        """Guards against a double-submit that slipped past idempotency —
        a second tab, or a client that retried with a fresh key."""
        ...


class InvoiceNumberGenerator(Protocol):
    """Gapless sequential numbering, per financial year.

    Not a Postgres ``SEQUENCE``: sequences do not roll back, so every failed
    transaction burns a number and leaves a gap an auditor will ask about.
    """

    async def next_number(self, *, issued_on: date, series: str = "INV") -> str: ...


class CommissionCalculator(Protocol):
    """The platform's cut. A port because it is a commercial policy that
    changes per vendor tier and per campaign, and the booking engine should not
    need redeploying when it does."""

    async def commission_for(
        self, *, vendor_id: uuid.UUID, property_id: uuid.UUID, amount: Money
    ) -> Money: ...
