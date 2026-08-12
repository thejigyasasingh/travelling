"""Rate limiting — sliding-window counters in Redis.

**Sliding window over fixed window.** A fixed window lets a client send the
full quota at 11:59:59 and again at 12:00:00 — double the intended rate at
exactly the boundary, which is precisely when a scripted attacker fires. The
sliding window weights the previous window by how much of it is still in view,
so the rate holds across boundaries. It costs one extra counter and no extra
round-trip.

**Not a sorted-set log.** ``ZADD``-per-request with ``ZREMRANGEBYSCORE`` is
exact, but stores one member per request — at 3k RPS that is memory Redis
cannot spare, and the trims are O(log n) on the single Redis thread. Two
integer counters approximate the same bound within a few percent, which is
what a protective control needs.

**The whole evaluation is one Lua script.** Read-then-write from Python races:
under concurrency, N workers each read "99 used" and each allow. Lua executes
atomically inside Redis, so the check and the increment cannot interleave.

**Fail-open by default, fail-closed on auth.** If Redis is unreachable, a
fail-closed limiter takes the entire API down because of a cache outage. But
login and OTP endpoints fail *closed* — an unlimited login endpoint is a
credential-stuffing invitation, and being unable to log in for a few minutes
is a far smaller incident than a compromised account.
"""

from __future__ import annotations

from dataclasses import dataclass

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.core.logging import get_logger

logger = get_logger(__name__)

# KEYS[1] current window counter, KEYS[2] previous window counter
# ARGV: now_ms, window_ms, limit, cost
_SLIDING_WINDOW = """
local now      = tonumber(ARGV[1])
local window   = tonumber(ARGV[2])
local limit    = tonumber(ARGV[3])
local cost     = tonumber(ARGV[4])

local elapsed  = now % window
local weight   = (window - elapsed) / window

local current  = tonumber(redis.call('GET', KEYS[1]) or '0')
local previous = tonumber(redis.call('GET', KEYS[2]) or '0')
local used     = math.floor(previous * weight + current)

if used + cost > limit then
    -- Retry when enough of the previous window has scrolled out.
    local retry = math.ceil((window - elapsed) / 1000)
    return {0, limit - used, retry}
end

local newval = redis.call('INCRBY', KEYS[1], cost)
if newval == cost then
    -- Two windows of TTL: the previous counter must outlive its own window
    -- so the weighting above can still read it.
    redis.call('PEXPIRE', KEYS[1], window * 2)
end
return {1, limit - used - cost, 0}
"""


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int
    limit: int

    def headers(self) -> dict[str, str]:
        """``X-RateLimit-*`` on every response, not only on 429s. A client that
        can see it is at 3 of 300 never needs to discover the limit by hitting
        it."""
        out = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(self.remaining, 0)),
        }
        if not self.allowed:
            out["Retry-After"] = str(self.retry_after)
        return out


class RedisRateLimiter:
    __slots__ = ("_client", "_script")

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client
        self._script = client.register_script(_SLIDING_WINDOW)

    async def check(
        self,
        identity: str,
        *,
        limit: int,
        window_seconds: int,
        cost: int = 1,
        fail_open: bool = True,
    ) -> RateLimitResult:
        """``identity`` is the bucket — ``ip:1.2.3.4``, ``user:<uuid>``,
        ``login:<email_hash>``. Choosing it is the policy decision; this
        function only counts.
        """
        window_ms = window_seconds * 1000
        try:
            now_ms = int((await self._client.time())[0] * 1000)  # Redis clock: pods disagree
        except RedisError:
            return self._on_backend_failure(identity, limit, fail_open)

        bucket = now_ms // window_ms
        keys = [f"rl:{{{identity}}}:{bucket}", f"rl:{{{identity}}}:{bucket - 1}"]

        try:
            allowed, remaining, retry = await self._script(
                keys=keys, args=[now_ms, window_ms, limit, cost]
            )
        except RedisError as exc:
            logger.warning("ratelimit_backend_error", identity=identity, error=str(exc))
            return self._on_backend_failure(identity, limit, fail_open)

        return RateLimitResult(
            allowed=bool(allowed),
            remaining=int(remaining),
            retry_after=int(retry) or 1,
            limit=limit,
        )

    @staticmethod
    def _on_backend_failure(identity: str, limit: int, fail_open: bool) -> RateLimitResult:
        if fail_open:
            return RateLimitResult(allowed=True, remaining=limit, retry_after=0, limit=limit)
        logger.warning("ratelimit_fail_closed", identity=identity)
        return RateLimitResult(allowed=False, remaining=0, retry_after=5, limit=limit)

    async def reset(self, identity: str) -> None:
        """Clear a bucket — used after a successful login so a user who
        fumbled their password three times is not still throttled."""
        try:
            async for key in self._client.scan_iter(match=f"rl:{{{identity}}}:*", count=50):
                await self._client.delete(key)
        except RedisError:  # pragma: no cover
            pass
