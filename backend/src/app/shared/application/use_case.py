"""Use-case base.

One class, one business operation, one ``execute``. Not a ``BookingService``
with fourteen methods and nine constructor dependencies, seven of which any
given method ignores.

This shape is chosen for a specific reason: the constructor arguments of a use
case *are* its dependency list. When ``ConfirmBookingUseCase`` needs a payment
gateway and a notification port, that is visible in one signature and a test
supplies two fakes. In a fat service the same information is spread across the
method bodies, and every test constructs the whole world.

Use cases orchestrate; they do not decide. The rules ("is this refundable?",
"what does this cost?") live in the domain. A use case that grows an ``if``
about business policy is a sign the rule belongs on an aggregate.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Actor:
    """Who is performing this operation.

    Passed explicitly instead of read from a request-scoped global. A Celery
    task, an admin CLI command and an HTTP request all produce one of these,
    so the same use case serves all three — and an authorisation test can
    simply construct the actor it wants.
    """

    user_id: uuid.UUID | None
    roles: frozenset[str] = frozenset()
    vendor_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None
    ip: str | None = None
    #: From the token, not the database. Guards that require a reachable
    #: address read this; the domain re-checks where it truly matters.
    email_verified: bool = False

    @property
    def is_anonymous(self) -> bool:
        return self.user_id is None

    def has_role(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))

    @classmethod
    def system(cls) -> Actor:
        """For background jobs. Distinguishable in audit logs from a real
        admin, which matters when reconstructing who cancelled a booking."""
        return cls(user_id=None, roles=frozenset({"system"}))


class UseCase[InputT, OutputT](ABC):
    """Interface for a single business operation."""

    @abstractmethod
    async def execute(self, data: InputT, actor: Actor) -> OutputT: ...


class Command[InputT, OutputT](UseCase[InputT, OutputT], ABC):
    """Mutates state. Runs against the primary, inside a Unit of Work,
    and may record domain events."""


class Query[InputT, OutputT](UseCase[InputT, OutputT], ABC):
    """Reads only.

    Separated from ``Command`` because the two have genuinely different needs:
    a query may go to the read replica, may be cached, and may bypass the
    domain model entirely to return a projection built by a hand-written SQL
    statement. Forcing reads through aggregates is how ORM-heavy systems end
    up hydrating 500 objects to render one list page.
    """
