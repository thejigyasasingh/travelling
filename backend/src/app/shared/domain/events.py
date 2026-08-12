"""Domain events.

An event is a **fact that already happened**, named in the past tense
(``BookingConfirmed``, not ``ConfirmBooking``). That naming is not style: a
consumer cannot veto an event, only react to it. If something can be refused,
it is a command and belongs in a use case.

Events are how modules stay decoupled. ``booking`` does not import
``notification``, ``search`` or ``payout``; it records ``BookingConfirmed`` and
those three react. Adding a fourth consumer touches no booking code, which is
the entire justification for the modular monolith.

Every event is:

* **Serialisable** — it crosses a process boundary via the outbox.
* **Versioned** — consumers deploy independently of producers, so a v1 handler
  must keep working after the producer starts emitting v2.
* **Self-contained** — it carries the data a consumer needs. Carrying only an
  ID forces a re-read, and a re-read 30 seconds later sees a *newer* state than
  the event describes, which silently corrupts anything that assumed otherwise.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar

from app.core.clock import utcnow


@dataclass(frozen=True, kw_only=True)
class DomainEvent(ABC):
    """Base for every domain event.

    Frozen: an event is a historical fact, and a consumer mutating one would
    change what the next consumer sees.
    """

    #: Stable wire name. Never rename — an in-flight outbox row or a consumer
    #: deployed one version behind will still be using the old string.
    event_type: ClassVar[str]
    #: Bump when the payload shape changes incompatibly; handlers switch on it.
    event_version: ClassVar[int] = 1
    #: Which aggregate this belongs to; drives outbox partitioning and ordering.
    aggregate_type: ClassVar[str]

    aggregate_id: uuid.UUID
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=utcnow)

    @abstractmethod
    def to_payload(self) -> dict[str, Any]:
        """JSON-serialisable body.

        Written by hand rather than derived from the dataclass fields, so that
        renaming a Python attribute cannot silently change the wire contract
        that a deployed consumer depends on.
        """

    def envelope(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "event_version": self.event_version,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": str(self.aggregate_id),
            "occurred_at": self.occurred_at.isoformat(),
            "payload": self.to_payload(),
        }
