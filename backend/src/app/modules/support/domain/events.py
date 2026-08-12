"""Support events."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar

from app.shared.domain.events import DomainEvent

AGGREGATE = "ticket"


@dataclass(frozen=True, kw_only=True)
class TicketOpened(DomainEvent):
    event_type: ClassVar[str] = "ticket.opened"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    subject: str
    category: str
    priority: str
    requester_email: str
    booking_id: uuid.UUID | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "ticket_id": str(self.aggregate_id),
            "reference": self.reference,
            "subject": self.subject,
            "category": self.category,
            "priority": self.priority,
            "requester_email": self.requester_email,
            "booking_id": str(self.booking_id) if self.booking_id else None,
        }


@dataclass(frozen=True, kw_only=True)
class TicketReplied(DomainEvent):
    """Carries only a preview.

    The full body stays in the database: an event goes through the outbox, the
    broker and every consumer's logs, and a support message contains whatever a
    distressed guest chose to type — including, sometimes, card details.
    """

    event_type: ClassVar[str] = "ticket.replied"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    requester_email: str
    from_staff: bool
    is_internal: bool
    preview: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "ticket_id": str(self.aggregate_id),
            "reference": self.reference,
            # Suppressed for an internal note: nothing about it should reach a
            # consumer that might notify the guest.
            "requester_email": None if self.is_internal else self.requester_email,
            "from_staff": self.from_staff,
            "is_internal": self.is_internal,
            "preview": "" if self.is_internal else self.preview,
        }


@dataclass(frozen=True, kw_only=True)
class TicketAssigned(DomainEvent):
    event_type: ClassVar[str] = "ticket.assigned"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    agent_id: uuid.UUID
    assigned_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "ticket_id": str(self.aggregate_id),
            "reference": self.reference,
            "agent_id": str(self.agent_id),
            "assigned_at": self.assigned_at.isoformat(),
        }


@dataclass(frozen=True, kw_only=True)
class TicketResolved(DomainEvent):
    event_type: ClassVar[str] = "ticket.resolved"
    aggregate_type: ClassVar[str] = AGGREGATE

    reference: str
    requester_email: str
    resolution: str
    resolved_at: datetime

    def to_payload(self) -> dict[str, Any]:
        return {
            "ticket_id": str(self.aggregate_id),
            "reference": self.reference,
            "requester_email": self.requester_email,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at.isoformat(),
        }
