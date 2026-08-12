"""Cache adapter.

Three decisions carry their weight here.

**Namespaced, versioned keys.** ``rw:v1:listing:{id}`` — the ``v1`` is a
schema epoch. When a cached DTO's shape changes, bumping the epoch invalidates
every affected key instantly, which is the only safe alternative to deploying
code that must tolerate both old and new payloads simultaneously.

**Stampede protection.** When a hot key expires under load, every concurrent
request misses and hits Postgres at once — the classic thundering herd that
turns a popular listing into an outage. :meth:`get_or_set` lets exactly one
caller recompute while the others briefly serve the stale value.

**Never fatal.** Every method swallows Redis transport errors and behaves as a
miss. The database is the source of truth; a cache outage must degrade
latency, not availability.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any, Final, TypeVar

import orjson
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

KEY_PREFIX: Final = "rw"
KEY_EPOCH: Final = "v1"
_LOCK_SUFFIX: Final = ":lock"
_RECOMPUTE_LOCK_TTL: Final = 30  # seconds; bounds a crashed recomputer


def cache_key(namespace: str, *parts: Any) -> str:
    joined = ":".join(str(p) for p in parts)
    return f"{KEY_PREFIX}:{KEY_EPOCH}:{namespace}:{joined}"


class RedisCache:
    """Implements :class:`app.shared.application.ports.CachePort`."""

    __slots__ = ("_client",)

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    # ── raw bytes ─────────────────────────────────────────────────────────

    async def get(self, key: str) -> bytes | None:
        try:
            return await self._client.get(key)  # type: ignore[no-any-return]
        except RedisError as exc:
            logger.warning("cache_get_failed", key=key, error=str(exc))
            return None

    async def set(self, key: str, value: bytes, ttl: timedelta) -> None:
        try:
            await self._client.set(key, value, ex=int(ttl.total_seconds()))
        except RedisError as exc:
            logger.warning("cache_set_failed", key=key, error=str(exc))

    async def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        try:
            return int(await self._client.delete(*keys))
        except RedisError as exc:
            logger.warning("cache_delete_failed", error=str(exc))
            return 0

    # ── JSON ──────────────────────────────────────────────────────────────

    async def get_json(self, key: str) -> Any | None:
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return orjson.loads(raw)
        except orjson.JSONDecodeError:
            # A poisoned value (bad deploy, manual edit) must not break reads.
            await self.delete(key)
            return None

    async def set_json(self, key: str, value: Any, ttl: timedelta) -> None:
        await self.set(key, orjson.dumps(value), ttl)

    # ── read-through with stampede protection ─────────────────────────────

    async def get_or_set(
        self,
        key: str,
        loader: Callable[[], Awaitable[T]],
        ttl: timedelta,
        *,
        lock_timeout: float = 3.0,
    ) -> T:
        """Return the cached value, else recompute exactly once.

        On a miss the caller races for a short ``SET NX`` lock. The winner runs
        ``loader``; losers poll briefly and use whatever the winner wrote. If
        the winner is slow, losers fall through and compute it themselves —
        correctness never depends on the lock, only efficiency does.
        """
        cached = await self.get_json(key)
        if cached is not None:
            return cached  # type: ignore[no-any-return]

        lock_key = key + _LOCK_SUFFIX
        got_lock = False
        try:
            got_lock = bool(await self._client.set(lock_key, b"1", nx=True, ex=_RECOMPUTE_LOCK_TTL))
        except RedisError:
            got_lock = True  # Redis down: everyone computes; DB is still correct

        if not got_lock:
            deadline = asyncio.get_running_loop().time() + lock_timeout
            while asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.05)
                if (value := await self.get_json(key)) is not None:
                    return value  # type: ignore[no-any-return]

        try:
            fresh = await loader()
            await self.set_json(key, fresh, ttl)
            return fresh
        finally:
            if got_lock:
                await self.delete(lock_key)

    # ── invalidation ──────────────────────────────────────────────────────

    async def invalidate_prefix(self, prefix: str) -> int:
        """Delete by prefix using ``SCAN``, never ``KEYS``.

        ``KEYS`` is O(n) over the entire keyspace and blocks the single Redis
        thread — on a production instance it is an outage. ``SCAN`` is
        incremental; deletions are batched so this stays cheap even when the
        prefix matches tens of thousands of keys.
        """
        pattern = f"{prefix}*" if not prefix.endswith("*") else prefix
        deleted = 0
        try:
            batch: list[str] = []
            async for key in self._client.scan_iter(match=pattern, count=500):
                batch.append(key)
                if len(batch) >= 500:
                    deleted += int(await self._client.delete(*batch))
                    batch.clear()
            if batch:
                deleted += int(await self._client.delete(*batch))
        except RedisError as exc:
            logger.warning("cache_invalidate_failed", prefix=prefix, error=str(exc))
        return deleted

    async def incr(self, key: str, ttl: timedelta, amount: int = 1) -> int:
        """Atomic counter with a TTL applied on creation (view counts, quotas)."""
        try:
            pipe = self._client.pipeline(transaction=True)
            pipe.incrby(key, amount)
            pipe.expire(key, int(ttl.total_seconds()), nx=True)
            result = await pipe.execute()
            return int(result[0])
        except RedisError:
            return 0
