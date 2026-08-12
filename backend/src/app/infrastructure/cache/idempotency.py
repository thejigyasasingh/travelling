"""Idempotency store for the ``Idempotency-Key`` header.

Mobile networks retry. Users double-tap "Pay". Load balancers replay a request
whose response was lost. Without this, each of those is a second booking and a
second charge.

The contract:

1. First request with a key **reserves** it atomically (``SET NX``) and runs.
2. A retry while the first is still running gets ``409 IN_PROGRESS`` — not a
   second execution, and not a wait that ties up a worker.
3. A retry after completion gets the **stored original response**, byte for
   byte, including the original status code.
4. The same key with a *different* body is a client bug and gets ``409``,
   because silently returning the first response would hide a real error.

The body fingerprint is what makes step 4 possible; storing the key alone
cannot distinguish a retry from key reuse.

Redis, not Postgres: the reservation is written before the transaction begins
and must survive its rollback. A row in the same transaction would roll back
with it and un-reserve the key precisely when a retry is most likely.
"""

from __future__ import annotations

import contextlib
import hashlib
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

import orjson
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.core.errors import IdempotencyConflictError, IdempotentRequestInProgressError
from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TTL: Final = timedelta(hours=24)
_IN_PROGRESS: Final = b"__in_progress__"


@dataclass(frozen=True, slots=True)
class StoredResponse:
    status_code: int
    body: Any
    headers: dict[str, str]


class RedisIdempotencyStore:
    __slots__ = ("_client",)

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    @staticmethod
    def fingerprint(method: str, path: str, body: bytes, actor: str) -> str:
        """Includes the actor so two users cannot collide on a client-chosen
        key — otherwise user B replaying user A's key would receive user A's
        booking confirmation."""
        digest = hashlib.sha256()
        digest.update(f"{method}\n{path}\n{actor}\n".encode())
        digest.update(body)
        return digest.hexdigest()

    @staticmethod
    def _key(key: str, actor: str) -> str:
        return f"idem:{actor}:{key}"

    async def begin(
        self, key: str, fingerprint: str, actor: str, ttl: timedelta = DEFAULT_TTL
    ) -> StoredResponse | None:
        """Reserve, or return the completed response to replay.

        Raises when the key is in flight or reused with a different body.
        """
        redis_key = self._key(key, actor)
        marker = _IN_PROGRESS + b":" + fingerprint.encode()

        try:
            reserved = await self._client.set(
                redis_key, marker, nx=True, ex=int(ttl.total_seconds())
            )
        except RedisError as exc:
            # Fail OPEN. Idempotency protects against duplicates; refusing all
            # writes because Redis is down is a worse failure than a rare
            # duplicate that reconciliation will catch.
            logger.error("idempotency_unavailable", error=str(exc))
            return None

        if reserved:
            return None  # first execution — caller proceeds

        existing = await self._client.get(redis_key)
        if existing is None:  # expired between SET NX and GET
            return None

        if existing.startswith(_IN_PROGRESS):
            stored_fp = existing.split(b":", 1)[1].decode()
            if stored_fp != fingerprint:
                raise IdempotencyConflictError
            raise IdempotentRequestInProgressError

        try:
            record = orjson.loads(existing)
        except orjson.JSONDecodeError:  # pragma: no cover
            return None

        if record.get("fingerprint") != fingerprint:
            raise IdempotencyConflictError

        return StoredResponse(
            status_code=record["status_code"],
            body=record["body"],
            headers=record.get("headers", {}),
        )

    async def complete(
        self,
        key: str,
        actor: str,
        fingerprint: str,
        response: StoredResponse,
        ttl: timedelta = DEFAULT_TTL,
    ) -> None:
        """Replace the in-progress marker with the real response."""
        payload = orjson.dumps(
            {
                "fingerprint": fingerprint,
                "status_code": response.status_code,
                "body": response.body,
                "headers": response.headers,
            }
        )
        try:
            await self._client.set(self._key(key, actor), payload, ex=int(ttl.total_seconds()))
        except RedisError as exc:  # pragma: no cover
            logger.error("idempotency_store_failed", error=str(exc))

    async def abandon(self, key: str, actor: str) -> None:
        """Drop the reservation when the handler failed.

        A 500 must not pin the key for 24 hours — the client's retry is exactly
        what we want to succeed. Only *successful* responses are worth
        replaying.
        """
        with contextlib.suppress(RedisError):  # pragma: no cover
            await self._client.delete(self._key(key, actor))
