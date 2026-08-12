"""Entities and aggregate roots.

These are **plain Python objects with no ORM inheritance**. Models are mapped
to them at the repository boundary (SQLAlchemy imperative mapping or explicit
translation), which costs a little code and buys three things:

1. Domain rules test in milliseconds with no database.
2. A schema change cannot silently rewrite a business rule.
3. Lazy loading cannot fire a query from inside a pricing calculation — the
   single most common source of N+1 in ORM-centric designs.

The distinction that matters:

* **Entity** — identity-based equality. Two ``Booking`` objects with the same
  id are the same booking, whatever their fields say.
* **Value object** — value-based equality, immutable. ``Money(500, "INR")`` is
  interchangeable with any other ``Money(500, "INR")``.
* **Aggregate root** — the *only* entity a repository loads or saves. It owns
  its children (a ``Booking`` owns its ``BookingRooms``) and enforces the
  invariants that span them. Anything outside references it by id, never by
  object pointer — that boundary is what makes the aggregate the unit of
  transactional consistency, and later the unit of sharding.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from uuid_utils.compat import uuid7

if TYPE_CHECKING:
    from app.shared.domain.events import DomainEvent


class Entity:
    """Identity-based equality and hashing."""

    __slots__ = ("id",)

    def __init__(self, entity_id: uuid.UUID | None = None) -> None:
        self.id: uuid.UUID = entity_id or uuid7()

    def __eq__(self, other: object) -> bool:
        if other.__class__ is not self.__class__:
            return NotImplemented
        return bool(self.id == other.id)

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.id))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} {self.id}>"


class AggregateRoot(Entity):
    """Entity that owns a consistency boundary and records what it did.

    Events are *recorded*, never published, from inside the aggregate. The
    aggregate has no idea whether a message broker exists; the Unit of Work
    drains them and writes them to the outbox in the same commit. That
    separation is why a domain rule stays testable without any infrastructure.
    """

    __slots__ = ("_events", "version")

    def __init__(self, entity_id: uuid.UUID | None = None, version: int = 1) -> None:
        super().__init__(entity_id)
        self.version = version
        self._events: list[DomainEvent] = []

    def record(self, event: DomainEvent) -> None:
        self._events.append(event)

    def pull_events(self) -> list[DomainEvent]:
        """Drain. Called once by the Unit of Work at commit time; draining
        rather than copying makes double-publication impossible."""
        events, self._events = self._events, []
        return events

    @property
    def has_pending_events(self) -> bool:
        return bool(self._events)


class ValueObject:
    """Marker for immutable, value-equal types.

    Prefer ``@dataclass(frozen=True, slots=True)`` — this exists so that
    ``isinstance(x, ValueObject)`` reads clearly in generic mapping code.
    """

    __slots__ = ()

    def __setattr__(self, name: str, value: Any) -> None:  # pragma: no cover
        msg = f"{type(self).__name__} is immutable"
        raise AttributeError(msg)
