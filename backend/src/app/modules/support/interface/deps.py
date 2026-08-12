"""Support wiring."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from app.interface.api.deps import ContainerDep
from app.modules.support.application.use_cases import (
    AssignTicket,
    GetTicket,
    OpenTicket,
    ReplyToTicket,
    ResolveTicket,
    SetTicketPriority,
)
from app.modules.support.infrastructure.unit_of_work import SupportUow


async def get_support_uow(container: ContainerDep) -> AsyncIterator[SupportUow]:
    async with container.database.write_session() as session:
        uow = SupportUow(session)
        yield uow
        await uow.flush()


SupportUowDep = Annotated[SupportUow, Depends(get_support_uow)]


def open_ticket_uc(container: ContainerDep, uow: SupportUowDep) -> OpenTicket:
    return OpenTicket(tickets=uow.tickets, clock=container.clock)


def reply_uc(container: ContainerDep, uow: SupportUowDep) -> ReplyToTicket:
    return ReplyToTicket(tickets=uow.tickets, clock=container.clock)


def get_ticket_uc(container: ContainerDep, uow: SupportUowDep) -> GetTicket:
    return GetTicket(tickets=uow.tickets, clock=container.clock)


def assign_uc(container: ContainerDep, uow: SupportUowDep) -> AssignTicket:
    return AssignTicket(tickets=uow.tickets, clock=container.clock)


def resolve_uc(container: ContainerDep, uow: SupportUowDep) -> ResolveTicket:
    return ResolveTicket(tickets=uow.tickets, clock=container.clock)


def set_priority_uc(container: ContainerDep, uow: SupportUowDep) -> SetTicketPriority:
    return SetTicketPriority(tickets=uow.tickets, clock=container.clock)
