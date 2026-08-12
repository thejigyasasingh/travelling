"""What the support use cases need from persistence."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.modules.support.domain.entities import Ticket


class TicketRepository(Protocol):
    async def get(self, ticket_id: uuid.UUID) -> Ticket | None: ...

    async def get_by_reference(self, reference: str) -> Ticket | None: ...

    async def add(self, ticket: Ticket) -> None: ...

    async def list_for_requester(
        self, *, user_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> tuple[list[Ticket], int]: ...

    async def list_for_admin(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        assigned_to: uuid.UUID | None = None,
        unassigned_only: bool = False,
        query: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Ticket], int]:
        """The agent queue: priority first, then age."""
        ...

    async def queue_counts(self) -> dict[str, int]: ...
