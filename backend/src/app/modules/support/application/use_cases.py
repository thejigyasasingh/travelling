"""Support use cases."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.clock import Clock
from app.core.logging import get_logger
from app.modules.support.application.dto import OpenTicketInput
from app.modules.support.application.ports import TicketRepository
from app.modules.support.domain import errors
from app.modules.support.domain.entities import Ticket
from app.modules.support.domain.reference import new_reference
from app.modules.support.domain.value_objects import (
    TicketCategory,
    TicketPriority,
)
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

STAFF_ROLES = ("support", "admin", "superadmin")


@dataclass(slots=True)
class OpenTicket:
    tickets: TicketRepository
    clock: Clock

    async def execute(self, data: OpenTicketInput, actor: Actor) -> Ticket:
        ticket = Ticket.open(
            reference=new_reference(),
            requester_id=actor.user_id,
            requester_name=data.requester_name,
            requester_email=data.requester_email,
            subject=data.subject,
            body=data.body,
            category=TicketCategory(data.category),
            now=self.clock.now(),
            booking_id=data.booking_id,
        )
        await self.tickets.add(ticket)
        logger.info(
            "ticket_opened",
            reference=ticket.reference,
            category=ticket.category.value,
            priority=ticket.priority.value,
        )
        return ticket


@dataclass(slots=True)
class ReplyToTicket:
    tickets: TicketRepository
    clock: Clock

    async def execute(
        self,
        *,
        ticket_id: uuid.UUID,
        body: str,
        actor: Actor,
        is_internal: bool = False,
    ) -> Ticket:
        ticket = await self.tickets.get(ticket_id)
        if ticket is None:
            raise errors.TicketNotFoundError

        is_staff = actor.has_role(*STAFF_ROLES)
        if not is_staff:
            _assert_own(ticket, actor)
            # A guest cannot write an internal note, whatever the request says.
            is_internal = False

        ticket.add_message(
            author_id=actor.user_id,
            author_name="Support" if is_staff else ticket.requester_name,
            body=body,
            now=self.clock.now(),
            from_staff=is_staff,
            is_internal=is_internal,
        )
        return ticket


@dataclass(slots=True)
class AssignTicket:
    tickets: TicketRepository
    clock: Clock

    async def execute(self, ticket_id: uuid.UUID, agent_id: uuid.UUID, actor: Actor) -> Ticket:
        ticket = await self._staff_ticket(ticket_id, actor)
        ticket.assign(agent_id=agent_id, now=self.clock.now())
        return ticket

    async def _staff_ticket(self, ticket_id: uuid.UUID, actor: Actor) -> Ticket:
        if not actor.has_role(*STAFF_ROLES):
            raise errors.TicketAccessDeniedError
        ticket = await self.tickets.get(ticket_id)
        if ticket is None:
            raise errors.TicketNotFoundError
        return ticket


@dataclass(slots=True)
class ResolveTicket:
    tickets: TicketRepository
    clock: Clock

    async def execute(self, ticket_id: uuid.UUID, resolution: str, actor: Actor) -> Ticket:
        if not actor.has_role(*STAFF_ROLES):
            raise errors.TicketAccessDeniedError
        ticket = await self.tickets.get(ticket_id)
        if ticket is None:
            raise errors.TicketNotFoundError
        ticket.resolve(resolution=resolution, now=self.clock.now())
        logger.info("ticket_resolved", reference=ticket.reference, by=str(actor.user_id))
        return ticket


@dataclass(slots=True)
class SetTicketPriority:
    tickets: TicketRepository
    clock: Clock

    async def execute(self, ticket_id: uuid.UUID, priority: str, actor: Actor) -> Ticket:
        if not actor.has_role(*STAFF_ROLES):
            raise errors.TicketAccessDeniedError
        ticket = await self.tickets.get(ticket_id)
        if ticket is None:
            raise errors.TicketNotFoundError
        ticket.set_priority(TicketPriority(priority))
        return ticket


@dataclass(slots=True)
class GetTicket:
    """One ticket, filtered for who is asking.

    `include_internal` is derived from the actor here rather than passed in by
    the caller. A route that forgets the flag would render agents' private
    notes to the guest they are about — so the decision is made once, next to
    the access check that already knows who this is.
    """

    tickets: TicketRepository
    clock: Clock

    async def execute(self, ticket_id: uuid.UUID, actor: Actor) -> tuple[Ticket, bool]:
        ticket = await self.tickets.get(ticket_id)
        if ticket is None:
            raise errors.TicketNotFoundError

        is_staff = actor.has_role(*STAFF_ROLES)
        if not is_staff:
            _assert_own(ticket, actor)
        return ticket, is_staff


def _assert_own(ticket: Ticket, actor: Actor) -> None:
    """404 at the interface, not 403 — a distinguishable refusal lets someone
    enumerate other people's support conversations."""
    if actor.user_id is None or ticket.requester_id != actor.user_id:
        raise errors.TicketAccessDeniedError
