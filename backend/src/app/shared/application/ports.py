"""Ports — the interfaces the application layer owns and infrastructure implements.

This is the inversion in "dependency inversion". A use case says "I need to
send an email"; it does not say "I need SES". The port is declared *here*, next
to the code that consumes it, and the adapter lives in ``app.infrastructure``.
The dependency arrow points inward, which is what lets us swap SES for
SendGrid, or S3 for MinIO, without a use case changing.

They are ``Protocol``s rather than ABCs deliberately: adapters do not import
this module to inherit from it, so infrastructure never appears in the
application layer's import graph — and a test double is just a small class,
with no base to subclass.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, Protocol, TypeVar, runtime_checkable

from app.core.types import Money

AggregateT = TypeVar("AggregateT")


@runtime_checkable
class Repository(Protocol[AggregateT]):
    """Collection-like access to one aggregate root.

    Note what is absent: no ``commit()``, no ``session``. Transaction control
    belongs to the Unit of Work. A repository that could commit would let one
    use case half-persist another's work.
    """

    async def get(self, aggregate_id: uuid.UUID) -> AggregateT | None: ...
    async def add(self, aggregate: AggregateT) -> None: ...


class UnitOfWorkPort(Protocol):
    """Transaction boundary as seen by a use case."""

    async def __aenter__(self) -> UnitOfWorkPort: ...
    async def __aexit__(self, *exc: Any) -> None: ...
    async def flush(self) -> None: ...


class CachePort(Protocol):
    async def get(self, key: str) -> bytes | None: ...
    async def set(self, key: str, value: bytes, ttl: timedelta) -> None: ...
    async def delete(self, *keys: str) -> int: ...
    async def invalidate_prefix(self, prefix: str) -> int: ...


class LockPort(Protocol):
    """Distributed mutex.

    Used for coarse serialisation (one payout run at a time, one import per
    vendor), never for booking inventory — that correctness lives in a database
    constraint, because a lock held by a process that dies mid-transaction
    protects nothing.
    """

    async def acquire(self, key: str, ttl: timedelta) -> str | None: ...
    async def release(self, key: str, token: str) -> bool: ...


class EventPublisherPort(Protocol):
    """Publishes an already-committed outbox row. Use cases never call this —
    they record events on the aggregate and the relay calls it."""

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None: ...


class NotificationPort(Protocol):
    async def send(
        self,
        *,
        user_id: uuid.UUID,
        template: str,
        context: dict[str, Any],
        channels: Sequence[str] | None = None,
    ) -> None: ...


class StoragePort(Protocol):
    """Object storage. Uploads are **presigned and direct to S3** — proxying a
    50 MB property photo through the API burns a worker for the duration of a
    mobile upload."""

    async def presign_upload(
        self, key: str, *, content_type: str, max_bytes: int
    ) -> dict[str, Any]: ...
    async def presign_download(self, key: str, *, expires_in: timedelta) -> str: ...
    async def delete(self, key: str) -> None: ...


class PaymentGatewayPort(Protocol):
    """Deliberately narrow. Everything gateway-specific — Razorpay's order
    object, Stripe's PaymentIntent — stays behind this line so adding a second
    gateway for a new market does not touch the booking use case."""

    async def create_intent(
        self, *, amount: Money, reference: str, metadata: dict[str, str]
    ) -> dict[str, Any]: ...
    async def capture(self, intent_id: str, amount: Money) -> dict[str, Any]: ...
    async def refund(self, payment_id: str, amount: Money, reason: str) -> dict[str, Any]: ...
    def verify_webhook(self, body: bytes, signature: str) -> bool: ...


class SearchIndexPort(Protocol):
    async def index(self, doc_id: str, document: dict[str, Any]) -> None: ...
    async def remove(self, doc_id: str) -> None: ...


class IdempotencyStorePort(Protocol):
    """Backs the ``Idempotency-Key`` header.

    ``reserve`` must be atomic: two concurrent retries of the same POST must
    result in exactly one execution, with the loser waiting rather than
    double-booking.
    """

    async def reserve(self, key: str, request_fingerprint: str, ttl: timedelta) -> bool: ...
    async def get_response(self, key: str) -> dict[str, Any] | None: ...
    async def store_response(self, key: str, response: dict[str, Any], ttl: timedelta) -> None: ...


class ClockPort(Protocol):
    def now(self) -> datetime: ...
