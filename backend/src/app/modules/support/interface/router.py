"""Support endpoints.

Guests open and follow their own tickets; agents work the queue. The split that
matters is **internal notes**: they are filtered out for anyone who is not
staff, and the decision is made in the use case rather than at each route, so a
new endpoint cannot forget it.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.interface.api.deps import ActorDep
from app.modules.auth.domain.rbac import Permission
from app.modules.auth.interface.permissions import RequirePermission
from app.modules.support.application.dto import OpenTicketInput
from app.modules.support.application.use_cases import (
    AssignTicket,
    GetTicket,
    OpenTicket,
    ReplyToTicket,
    ResolveTicket,
    SetTicketPriority,
)
from app.modules.support.domain.entities import Ticket
from app.modules.support.interface import deps
from app.modules.support.interface.schemas import (
    AssignRequest,
    OpenTicketRequest,
    ReplyRequest,
    ResolveRequest,
    SetPriorityRequest,
    TicketCountsResponse,
    TicketListResponse,
    TicketMessageResponse,
    TicketResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/support/tickets", tags=["support"])
admin_router = APIRouter(prefix="/admin/tickets", tags=["admin: support"])

CanReadAny = Depends(RequirePermission(Permission.TICKET_READ_ANY))
CanResolve = Depends(RequirePermission(Permission.TICKET_RESOLVE_ANY))


def _to_response(ticket: Ticket, *, include_internal: bool) -> TicketResponse:
    from app.core.clock import utcnow

    return TicketResponse(
        id=ticket.id,
        reference=ticket.reference,
        subject=ticket.subject,
        category=ticket.category.value,
        priority=ticket.priority.value,
        status=ticket.status.value,
        requester_name=ticket.requester_name,
        requester_email=ticket.requester_email,
        booking_id=ticket.booking_id,
        assigned_to=ticket.assigned_to,
        opened_at=ticket.opened_at,
        first_responded_at=ticket.first_responded_at,
        resolved_at=ticket.resolved_at,
        resolution=ticket.resolution,
        response_due_at=ticket.response_due_at(),
        is_breaching=ticket.is_breaching(utcnow()),
        messages=[
            TicketMessageResponse(
                id=m.id,
                author_name=m.author_name,
                body=m.body,
                is_internal=m.is_internal,
                sent_at=m.sent_at,
            )
            # The filter that matters. `include_internal` comes from the use
            # case, which derived it from the actor.
            for m in ticket.visible_messages(include_internal=include_internal)
        ],
    )


# ══════════════════════════════════════════════════════════════════════════
# Guest
# ══════════════════════════════════════════════════════════════════════════


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TicketResponse,
    summary="Open a ticket",
)
async def open_ticket(
    body: OpenTicketRequest,
    actor: ActorDep,
    use_case: Annotated[OpenTicket, Depends(deps.open_ticket_uc)],
) -> TicketResponse:
    """Priority is derived from the category, not asked for.

    Everything would be urgent if guests set it themselves — and then nothing
    would be. A `check_in` ticket is urgent because the guest is standing
    outside a door; that judgement belongs to the platform.
    """
    if not body.requester_email:
        # The token carries an id, not an address, so a signed-in guest who
        # omits it is asked for one rather than having a blank recorded — a
        # ticket nobody can reply to is worse than a validation error.
        raise ValidationError("An email address is required so we can reply.")
    ticket = await use_case.execute(
        OpenTicketInput(
            subject=body.subject,
            body=body.body,
            category=body.category,
            requester_name=body.requester_name or "Guest",
            requester_email=body.requester_email,
            booking_id=body.booking_id,
        ),
        actor,
    )
    return _to_response(ticket, include_internal=False)


@router.get("", response_model=TicketListResponse, summary="Your tickets")
async def my_tickets(
    uow: deps.SupportUowDep,
    actor: ActorDep,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> TicketListResponse:
    tickets, total = await uow.tickets.list_for_requester(
        user_id=actor.user_id,  # type: ignore[arg-type]
        limit=size,
        offset=(page - 1) * size,
    )
    return TicketListResponse(
        items=[_to_response(t, include_internal=False) for t in tickets],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{ticket_id}", response_model=TicketResponse, summary="One ticket")
async def get_ticket(
    ticket_id: uuid.UUID,
    actor: ActorDep,
    use_case: Annotated[GetTicket, Depends(deps.get_ticket_uc)],
) -> TicketResponse:
    """Someone else's ticket is **404**, never 403 — a distinguishable refusal
    lets an attacker enumerate support conversations, which carry booking
    references and contact details."""
    ticket, is_staff = await use_case.execute(ticket_id, actor)
    return _to_response(ticket, include_internal=is_staff)


@router.post("/{ticket_id}/reply", response_model=TicketResponse, summary="Reply to a ticket")
async def reply(
    ticket_id: uuid.UUID,
    body: ReplyRequest,
    actor: ActorDep,
    use_case: Annotated[ReplyToTicket, Depends(deps.reply_uc)],
) -> TicketResponse:
    ticket = await use_case.execute(
        ticket_id=ticket_id, body=body.body, actor=actor, is_internal=body.internal
    )
    is_staff = actor.has_role("support", "admin", "superadmin")
    return _to_response(ticket, include_internal=is_staff)


# ══════════════════════════════════════════════════════════════════════════
# Agent queue
# ══════════════════════════════════════════════════════════════════════════


@admin_router.get(
    "",
    response_model=TicketListResponse,
    dependencies=[CanReadAny],
    summary="The queue",
)
async def queue(
    uow: deps.SupportUowDep,
    actor: ActorDep,
    status_filter: Annotated[str | None, Query(alias="status")] = "open",
    priority: str | None = None,
    assigned_to: uuid.UUID | None = None,
    unassigned: bool = False,
    q: Annotated[str | None, Query(max_length=120)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TicketListResponse:
    """Sorted by priority, then age.

    Not reverse-chronological: an urgent ticket opened five minutes ago matters
    more than a low one from yesterday, and a queue that shows the newest first
    buries exactly the thing an agent should pick up.
    """
    tickets, total = await uow.tickets.list_for_admin(
        status=status_filter,
        priority=priority,
        assigned_to=assigned_to,
        unassigned_only=unassigned,
        query=q,
        limit=size,
        offset=(page - 1) * size,
    )
    return TicketListResponse(
        items=[_to_response(t, include_internal=True) for t in tickets],
        total=total,
        page=page,
        size=size,
    )


@admin_router.get(
    "/counts",
    response_model=TicketCountsResponse,
    dependencies=[CanReadAny],
    summary="Queue depth by status",
)
async def counts(uow: deps.SupportUowDep, actor: ActorDep) -> TicketCountsResponse:
    return TicketCountsResponse(counts=await uow.tickets.queue_counts())


@admin_router.post(
    "/{ticket_id}/assign",
    response_model=TicketResponse,
    dependencies=[CanReadAny],
    summary="Assign to an agent",
)
async def assign(
    ticket_id: uuid.UUID,
    body: AssignRequest,
    actor: ActorDep,
    use_case: Annotated[AssignTicket, Depends(deps.assign_uc)],
) -> TicketResponse:
    ticket = await use_case.execute(ticket_id, body.agent_id, actor)
    return _to_response(ticket, include_internal=True)


@admin_router.post(
    "/{ticket_id}/resolve",
    response_model=TicketResponse,
    dependencies=[CanResolve],
    summary="Resolve",
)
async def resolve(
    ticket_id: uuid.UUID,
    body: ResolveRequest,
    actor: ActorDep,
    use_case: Annotated[ResolveTicket, Depends(deps.resolve_uc)],
) -> TicketResponse:
    """A resolution note is required.

    One nobody wrote down is one the next agent cannot use when the guest
    writes back a week later — which they do.
    """
    ticket = await use_case.execute(ticket_id, body.resolution, actor)
    return _to_response(ticket, include_internal=True)


@admin_router.patch(
    "/{ticket_id}/priority",
    response_model=TicketResponse,
    dependencies=[CanReadAny],
    summary="Re-prioritise",
)
async def set_priority(
    ticket_id: uuid.UUID,
    body: SetPriorityRequest,
    actor: ActorDep,
    use_case: Annotated[SetTicketPriority, Depends(deps.set_priority_uc)],
) -> TicketResponse:
    ticket = await use_case.execute(ticket_id, body.priority, actor)
    return _to_response(ticket, include_internal=True)
