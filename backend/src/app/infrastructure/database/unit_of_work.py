"""Unit of Work.

Owns the transaction boundary so use cases never call ``commit()``. That single
rule is what makes the transactional outbox safe: domain events are appended to
the same session and therefore land in the *same commit* as the state change
they describe. Publishing after commit — ``task.delay()`` on the next line —
loses the event whenever the process dies in between, and a booking confirmed
with no confirmation email sent is undetectable after the fact.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Protocol, Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)


class DomainEvent(Protocol):
    """Structural type. The domain layer defines the real base class; the
    infrastructure layer only needs these three attributes to persist it."""

    aggregate_type: str
    aggregate_id: Any
    event_type: str

    def to_payload(self) -> dict[str, Any]: ...


class UnitOfWork(Protocol):
    session: AsyncSession

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc: Any) -> None: ...
    async def flush(self) -> None: ...
    def add_event(self, event: DomainEvent) -> None: ...


class SqlUnitOfWork:
    """Concrete UoW over an ``AsyncSession``.

    Repositories are attached by the container as the modules land; this class
    intentionally knows nothing about them.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._events: list[DomainEvent] = []
        self._closed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
            return
        await self.commit()

    def add_event(self, event: DomainEvent) -> None:
        """Queue a domain event. Written to the outbox inside the commit."""
        self._events.append(event)

    async def flush(self) -> None:
        """Force SQL without ending the transaction — needed when a later
        statement depends on a server-side default or a constraint check."""
        await self.session.flush()

    async def commit(self) -> None:
        if self._closed:
            return
        if self._events:
            await self._write_outbox()
        await self.session.commit()
        self._closed = True
        if self._events:
            logger.debug("uow_committed_with_events", event_count=len(self._events))
        self._events.clear()

    async def rollback(self) -> None:
        if self._closed:
            return
        await self.session.rollback()
        self._closed = True
        self._events.clear()

    async def _write_outbox(self) -> None:
        """Append queued events to the ``outbox`` table in this transaction.

        Wired once the outbox model lands (migration 0009). Kept as an explicit
        seam so the commit path is already correct and no later change has to
        touch every use case.
        """
        from app.infrastructure.database.outbox import persist_events

        await persist_events(self.session, self._events)
