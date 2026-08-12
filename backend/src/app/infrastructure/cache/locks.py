"""Distributed locks.

Single-instance Redis lock (``SET NX PX`` + a token-checked Lua release), not
Redlock. Redlock's multi-master ceremony buys very little in exchange for real
complexity, and it is still not a correctness guarantee under GC pauses or
network partitions.

**Where this lock is and is not used** — this is the important part:

* **Used** for coarse serialisation where a duplicate run is wasteful but not
  wrong: nightly payout batches, per-vendor bulk imports, sitemap generation,
  one price-sync per property at a time.
* **Never used** for booking inventory. A lock holder that is paused by GC past
  its TTL believes it holds a lock it does not, and two "holders" then both
  write. Overbooking is prevented by a Postgres exclusion constraint inside the
  booking transaction, where the database — not a hopeful client — enforces it.

The release script checks the token so a process whose lock already expired
cannot delete the *next* holder's lock, which is the classic way a naive
``DEL``-based lock corrupts everything downstream.
"""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.core.logging import get_logger

logger = get_logger(__name__)

_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

_EXTEND_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return 0
"""


class LockAcquisitionError(RuntimeError):
    """Could not acquire within the timeout. Callers decide whether to skip
    (a periodic job) or fail (a user-triggered action)."""


class RedisLockManager:
    """Implements :class:`app.shared.application.ports.LockPort`."""

    __slots__ = ("_client", "_extend", "_release")

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client
        self._release = client.register_script(_RELEASE_SCRIPT)
        self._extend = client.register_script(_EXTEND_SCRIPT)

    async def acquire(self, key: str, ttl: timedelta) -> str | None:
        """Returns the fencing token, or ``None`` if held elsewhere.

        The TTL is mandatory and non-negotiable: a lock without one is
        permanently held the moment a holder is OOM-killed.
        """
        token = secrets.token_urlsafe(16)
        try:
            acquired = await self._client.set(
                f"lock:{key}", token, nx=True, px=int(ttl.total_seconds() * 1000)
            )
        except RedisError as exc:
            # Fail CLOSED. An unacquirable lock skips a batch job; a wrongly
            # granted one runs a payout twice.
            logger.error("lock_acquire_failed", key=key, error=str(exc))
            return None
        return token if acquired else None

    async def release(self, key: str, token: str) -> bool:
        try:
            return bool(await self._release(keys=[f"lock:{key}"], args=[token]))
        except RedisError as exc:
            logger.warning("lock_release_failed", key=key, error=str(exc))
            return False  # the TTL will clean up

    async def extend(self, key: str, token: str, ttl: timedelta) -> bool:
        """Heartbeat for a job that legitimately outlives its initial TTL.

        Preferable to setting a long TTL up front: a long TTL means a crashed
        holder blocks the job for that long.
        """
        try:
            return bool(
                await self._extend(
                    keys=[f"lock:{key}"], args=[token, int(ttl.total_seconds() * 1000)]
                )
            )
        except RedisError:
            return False

    @asynccontextmanager
    async def guard(
        self, key: str, ttl: timedelta = timedelta(seconds=60), *, required: bool = True
    ) -> AsyncIterator[str | None]:
        """Scoped lock. ``required=False`` yields ``None`` instead of raising —
        the right behaviour for periodic jobs, where "another pod is already
        doing it" is success, not failure.
        """
        token = await self.acquire(key, ttl)
        if token is None:
            if required:
                raise LockAcquisitionError(f"Could not acquire lock {key!r}")
            logger.info("lock_skipped", key=key)
            yield None
            return
        try:
            yield token
        finally:
            await self.release(key, token)
