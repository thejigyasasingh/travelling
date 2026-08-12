"""Support value objects."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    #: The ball is with the guest. Distinguished from `in_progress` so the
    #: queue does not count tickets nobody is blocked on.
    WAITING_ON_GUEST = "waiting_on_guest"
    RESOLVED = "resolved"
    CLOSED = "closed"

    @property
    def is_open(self) -> bool:
        return self in (
            TicketStatus.OPEN,
            TicketStatus.IN_PROGRESS,
            TicketStatus.WAITING_ON_GUEST,
        )


class TicketPriority(StrEnum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"

    @property
    def first_response_target(self) -> timedelta:
        """How long until a first reply is late.

        Aggressive at the top end on purpose: `urgent` is reserved for a guest
        who cannot get into a property they have paid for, and an hour is
        already a long time to stand outside one.
        """
        return {
            TicketPriority.URGENT: timedelta(hours=1),
            TicketPriority.HIGH: timedelta(hours=4),
            TicketPriority.NORMAL: timedelta(hours=24),
            TicketPriority.LOW: timedelta(days=3),
        }[self]

    @property
    def rank(self) -> int:
        """For sorting a queue. Lower sorts first."""
        return {
            TicketPriority.URGENT: 0,
            TicketPriority.HIGH: 1,
            TicketPriority.NORMAL: 2,
            TicketPriority.LOW: 3,
        }[self]


class TicketCategory(StrEnum):
    BOOKING = "booking"
    PAYMENT = "payment"
    REFUND = "refund"
    PROPERTY = "property"
    ACCOUNT = "account"
    #: A guest who cannot check in. Always urgent — they are standing outside.
    CHECK_IN = "check_in"
    OTHER = "other"

    @property
    def default_priority(self) -> TicketPriority:
        """Derived from the category rather than asked of the guest.

        Everything would be urgent if guests set it themselves, and then
        nothing would be.
        """
        return {
            TicketCategory.CHECK_IN: TicketPriority.URGENT,
            TicketCategory.PAYMENT: TicketPriority.HIGH,
            TicketCategory.REFUND: TicketPriority.HIGH,
            TicketCategory.BOOKING: TicketPriority.NORMAL,
            TicketCategory.PROPERTY: TicketPriority.NORMAL,
            TicketCategory.ACCOUNT: TicketPriority.NORMAL,
            TicketCategory.OTHER: TicketPriority.LOW,
        }[self]

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()
