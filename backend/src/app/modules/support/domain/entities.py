"""Support tickets.

A ticket is a conversation with a deadline. Two things shape the model:

**Internal notes and guest replies live in the same thread, flagged.** Keeping
them in separate tables guarantees that one day a query forgets the filter and
an internal note — "guest is lying, see previous refund" — is rendered to the
guest. One table with an explicit `is_internal` flag makes the dangerous case
the one you have to opt into.

**First response time is recorded, not derived.** Support SLAs are measured on
"when did a human first reply", and reconstructing that later from message
timestamps means re-deriving it slightly differently in every report.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Final

from app.modules.support.domain import errors
from app.modules.support.domain.events import (
    TicketAssigned,
    TicketOpened,
    TicketReplied,
    TicketResolved,
)
from app.modules.support.domain.value_objects import (
    TicketCategory,
    TicketPriority,
    TicketStatus,
)
from app.shared.domain.entity import AggregateRoot, Entity

_TRANSITIONS: Final[dict[TicketStatus, frozenset[TicketStatus]]] = {
    TicketStatus.OPEN: frozenset(
        {TicketStatus.IN_PROGRESS, TicketStatus.WAITING_ON_GUEST, TicketStatus.RESOLVED}
    ),
    TicketStatus.IN_PROGRESS: frozenset({TicketStatus.WAITING_ON_GUEST, TicketStatus.RESOLVED}),
    # A guest replying reopens it — see `add_message`.
    TicketStatus.WAITING_ON_GUEST: frozenset({TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED}),
    TicketStatus.RESOLVED: frozenset({TicketStatus.CLOSED, TicketStatus.IN_PROGRESS}),
    # Terminal. A closed ticket is history; a new problem is a new ticket.
    TicketStatus.CLOSED: frozenset(),
}


class TicketMessage(Entity):
    """One message in the thread."""

    __slots__ = ("author_id", "author_name", "body", "is_internal", "sent_at")

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        author_id: uuid.UUID | None,
        author_name: str,
        body: str,
        sent_at: datetime,
        is_internal: bool = False,
    ) -> None:
        super().__init__(entity_id)
        self.author_id = author_id
        self.author_name = author_name
        self.body = body
        self.sent_at = sent_at
        #: Never rendered to the requester. See the module docstring.
        self.is_internal = is_internal


class Ticket(AggregateRoot):
    """A support conversation."""

    __slots__ = (
        "assigned_to",
        "booking_id",
        "category",
        "closed_at",
        "first_responded_at",
        "messages",
        "opened_at",
        "priority",
        "reference",
        "requester_email",
        "requester_id",
        "requester_name",
        "resolution",
        "resolved_at",
        "status",
        "subject",
    )

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        reference: str,
        requester_id: uuid.UUID | None,
        requester_name: str,
        requester_email: str,
        subject: str,
        category: TicketCategory,
        priority: TicketPriority,
        opened_at: datetime,
        status: TicketStatus = TicketStatus.OPEN,
        booking_id: uuid.UUID | None = None,
        assigned_to: uuid.UUID | None = None,
        first_responded_at: datetime | None = None,
        resolved_at: datetime | None = None,
        closed_at: datetime | None = None,
        resolution: str | None = None,
        messages: list[TicketMessage] | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(entity_id, version)
        self.reference = reference
        self.requester_id = requester_id
        self.requester_name = requester_name
        self.requester_email = requester_email
        self.subject = subject
        self.category = category
        self.priority = priority
        self.opened_at = opened_at
        self.status = status
        self.booking_id = booking_id
        self.assigned_to = assigned_to
        self.first_responded_at = first_responded_at
        self.resolved_at = resolved_at
        self.closed_at = closed_at
        self.resolution = resolution
        self.messages = messages or []

    @classmethod
    def open(
        cls,
        *,
        reference: str,
        requester_id: uuid.UUID | None,
        requester_name: str,
        requester_email: str,
        subject: str,
        body: str,
        category: TicketCategory,
        now: datetime,
        booking_id: uuid.UUID | None = None,
        priority: TicketPriority | None = None,
    ) -> Ticket:
        if not subject.strip():
            raise errors.InvalidTicketError("subject", "is required")
        if len(body.strip()) < 10:
            raise errors.InvalidTicketError("body", "needs a little more detail")

        ticket = cls(
            reference=reference,
            requester_id=requester_id,
            requester_name=requester_name.strip(),
            requester_email=requester_email.lower().strip(),
            subject=subject.strip()[:200],
            category=category,
            # Derived from the category unless a human overrides it: a guest
            # cannot be trusted to set their own priority, and everything would
            # be urgent if they could.
            priority=priority or category.default_priority,
            opened_at=now,
            booking_id=booking_id,
        )
        ticket.messages.append(
            TicketMessage(
                author_id=requester_id,
                author_name=ticket.requester_name,
                body=body.strip(),
                sent_at=now,
            )
        )
        ticket.record(
            TicketOpened(
                aggregate_id=ticket.id,
                reference=reference,
                subject=ticket.subject,
                category=category.value,
                priority=ticket.priority.value,
                requester_email=ticket.requester_email,
                booking_id=booking_id,
            )
        )
        return ticket

    # ── conversation ──────────────────────────────────────────────────────

    def add_message(
        self,
        *,
        author_id: uuid.UUID | None,
        author_name: str,
        body: str,
        now: datetime,
        from_staff: bool,
        is_internal: bool = False,
    ) -> TicketMessage:
        if self.status is TicketStatus.CLOSED:
            raise errors.TicketClosedError(self.reference)
        if not body.strip():
            raise errors.InvalidTicketError("body", "is required")

        message = TicketMessage(
            author_id=author_id,
            author_name=author_name,
            body=body.strip(),
            sent_at=now,
            is_internal=is_internal and from_staff,
        )
        self.messages.append(message)

        if from_staff:
            # An internal note is not a response to the guest, so it must not
            # stop the SLA clock — that is how a team looks compliant while
            # nobody has actually replied.
            if not message.is_internal and self.first_responded_at is None:
                self.first_responded_at = now
            if not message.is_internal and self.status in (
                TicketStatus.OPEN,
                TicketStatus.IN_PROGRESS,
            ):
                self.status = TicketStatus.WAITING_ON_GUEST
        elif self.status in (TicketStatus.WAITING_ON_GUEST, TicketStatus.RESOLVED):
            # The guest came back. A resolved ticket they reply to is not
            # resolved, whatever the queue would prefer.
            self.status = TicketStatus.IN_PROGRESS
            self.resolved_at = None

        self.record(
            TicketReplied(
                aggregate_id=self.id,
                reference=self.reference,
                requester_email=self.requester_email,
                from_staff=from_staff,
                is_internal=message.is_internal,
                preview=message.body[:120],
            )
        )
        return message

    def assign(self, *, agent_id: uuid.UUID, now: datetime) -> None:
        if self.status is TicketStatus.CLOSED:
            raise errors.TicketClosedError(self.reference)
        self.assigned_to = agent_id
        if self.status is TicketStatus.OPEN:
            self._transition(TicketStatus.IN_PROGRESS)
        self.record(
            TicketAssigned(
                aggregate_id=self.id,
                reference=self.reference,
                agent_id=agent_id,
                assigned_at=now,
            )
        )

    def set_priority(self, priority: TicketPriority) -> None:
        self.priority = priority

    def resolve(self, *, resolution: str, now: datetime) -> None:
        if not resolution.strip():
            # A resolution nobody wrote down is one the next agent cannot use
            # when the guest writes back a week later.
            raise errors.InvalidTicketError("resolution", "is required to resolve a ticket")
        self._transition(TicketStatus.RESOLVED)
        self.resolution = resolution.strip()
        self.resolved_at = now
        self.record(
            TicketResolved(
                aggregate_id=self.id,
                reference=self.reference,
                requester_email=self.requester_email,
                resolution=self.resolution,
                resolved_at=now,
            )
        )

    def close(self, *, now: datetime) -> None:
        self._transition(TicketStatus.CLOSED)
        self.closed_at = now

    def reopen(self) -> None:
        self._transition(TicketStatus.IN_PROGRESS)
        self.resolved_at = None

    def _transition(self, target: TicketStatus) -> None:
        if target not in _TRANSITIONS.get(self.status, frozenset()):
            raise errors.InvalidTicketTransitionError(self.status.value, target.value)
        self.status = target

    # ── what the queue sorts on ───────────────────────────────────────────

    def response_due_at(self) -> datetime:
        return self.opened_at + self.priority.first_response_target

    def is_breaching(self, now: datetime) -> bool:
        """No first reply and the target has passed.

        Used to sort the queue, so the ticket most at risk is the one an agent
        sees first — rather than the oldest, which may already be lost.
        """
        return self.first_responded_at is None and now > self.response_due_at()

    def visible_messages(self, *, include_internal: bool) -> list[TicketMessage]:
        """The thread, filtered.

        Callers must be explicit about internal notes. The default in every
        guest-facing path is `False`, and the type system makes forgetting it a
        missing-argument error rather than a leak.
        """
        if include_internal:
            return list(self.messages)
        return [m for m in self.messages if not m.is_internal]

    def as_audit(self) -> dict[str, Any]:
        return {
            "ticket_id": str(self.id),
            "reference": self.reference,
            "status": self.status.value,
            "priority": self.priority.value,
        }
