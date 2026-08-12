"""Redis connection management.

**One pool per logical DB, not one shared client.** Redis is single-threaded:
a slow ``KEYS`` from a debugging session, or a rate-limiter Lua script under a
traffic spike, blocks every other command on that connection pool. Separating
cache / locks / rate limiting / broker / pubsub means a problem in one is
contained, and each can be moved to its own cluster later by changing a URL
rather than by finding every call site.

**Timeouts are aggressive (2s) and failures are non-fatal for cache reads.**
Redis is an optimisation, not a source of truth. A cache lookup that hangs for
30 seconds is far worse than one that fails in 2 and falls through to
Postgres — the former converts a Redis blip into a total outage as every
worker blocks.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RedisDB(IntEnum):
    """Logical databases. Named so a call site says what it is for."""

    CACHE = 0
    LOCK = 1
    RATELIMIT = 2
    BROKER = 3
    PUBSUB = 4


class RedisRegistry:
    """Owns every Redis pool. Constructed once by the container."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._clients: dict[RedisDB, aioredis.Redis] = {}

    def _create(self, db: RedisDB) -> aioredis.Redis:
        cfg = self._settings.redis
        db_index = {
            RedisDB.CACHE: cfg.cache_db,
            RedisDB.LOCK: cfg.lock_db,
            RedisDB.RATELIMIT: cfg.ratelimit_db,
            RedisDB.BROKER: cfg.broker_db,
            RedisDB.PUBSUB: cfg.pubsub_db,
        }[db]

        client: aioredis.Redis = aioredis.Redis.from_url(
            cfg.dsn_for(db_index),
            max_connections=cfg.max_connections,
            socket_timeout=cfg.socket_timeout_seconds,
            socket_connect_timeout=cfg.socket_timeout_seconds,
            socket_keepalive=True,
            health_check_interval=30,
            # Retry only on transport faults — never on a timeout of a command
            # that may have already executed. Retrying a non-idempotent INCR
            # after a timeout double-counts.
            retry=Retry(ExponentialBackoff(base=0.05, cap=0.5), retries=2),
            retry_on_error=[RedisConnectionError],
            decode_responses=False,  # bytes in, bytes out; callers own serialisation
        )
        return client

    def client(self, db: RedisDB) -> aioredis.Redis:
        if db not in self._clients:
            self._clients[db] = self._create(db)
        return self._clients[db]

    @property
    def cache(self) -> aioredis.Redis:
        return self.client(RedisDB.CACHE)

    @property
    def locks(self) -> aioredis.Redis:
        return self.client(RedisDB.LOCK)

    @property
    def ratelimit(self) -> aioredis.Redis:
        return self.client(RedisDB.RATELIMIT)

    @property
    def pubsub(self) -> aioredis.Redis:
        return self.client(RedisDB.PUBSUB)

    async def ping(self, db: RedisDB = RedisDB.CACHE) -> bool:
        return bool(await self.client(db).ping())

    async def info(self) -> dict[str, Any]:
        """Used by the readiness probe and the ops dashboard."""
        raw: dict[str, Any] = await self.cache.info("memory")
        return {
            "used_memory_human": raw.get("used_memory_human"),
            "maxmemory_human": raw.get("maxmemory_human"),
        }

    async def close(self) -> None:
        for db, client in self._clients.items():
            try:
                await client.aclose()
            except (RedisConnectionError, RedisTimeoutError):  # pragma: no cover
                logger.warning("redis_close_failed", db=db.name)
        self._clients.clear()
        logger.info("redis_pools_closed")
