"""Per-user spending limits.

The one dependency in this platform that bills per call and can be driven by
anyone with a keyboard. A booking costs us nothing until it is paid for; an
itinerary costs money the moment someone asks, and asking is free.

Checked **before** the call, in Redis, with a fixed window keyed to the period.
Not a sliding window: the extra precision buys nothing here, and the fixed
window's key encodes its own expiry so there is no sweep to run and no way for
a counter to outlive its meaning.

Fails **closed**, which is the opposite of the request rate limiter's policy in
the same codebase, and deliberately. Rate limiting protects the service, so
letting traffic through when Redis is down is the safe error. This protects the
budget, so the safe error is refusing — a Redis outage that silently uncaps
spend is the failure you find out about from the invoice.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.modules.ai.domain import errors

logger = get_logger(__name__)


class Feature(StrEnum):
    ITINERARY = "itinerary"
    CHAT = "chat"
    DESTINATIONS = "destinations"


class Period(StrEnum):
    HOUR = "hour"
    DAY = "day"


#: Two days. Long enough that a key outlives the window it counts even with
#: clock skew, short enough that abandoned keys clear themselves.
_TTL_SECONDS = 2 * 24 * 60 * 60


class Budget(Protocol):
    async def consume(
        self, *, user_id: uuid.UUID | None, feature: Feature, limit: int, period: Period
    ) -> None: ...


def _window(period: Period, now: datetime) -> tuple[str, int]:
    """The current window's key suffix, and seconds until it resets."""
    if period is Period.HOUR:
        return now.strftime("%Y%m%d%H"), 3600 - (now.minute * 60 + now.second)
    end_of_day = 86_400 - (now.hour * 3600 + now.minute * 60 + now.second)
    return now.strftime("%Y%m%d"), end_of_day


@dataclass(slots=True)
class RedisBudget:
    """Implements :class:`Budget`."""

    client: aioredis.Redis

    async def consume(
        self, *, user_id: uuid.UUID | None, feature: Feature, limit: int, period: Period
    ) -> None:
        """Increment, then check.

        Increment-first is what makes this correct under concurrency: two
        simultaneous requests both increment and the second sees 2, whereas a
        read-then-write lets both see 1 and both proceed. The cost is that a
        request refused at the boundary still consumed a slot, which is the
        right trade for a spend cap.

        A limit of 0 disables the feature for everyone — a kill switch that
        does not require a deploy.
        """
        if limit <= 0:
            raise errors.AIBudgetExceededError(feature.value, 0)

        now = datetime.now(UTC)
        suffix, resets_in = _window(period, now)
        # Anonymous callers share one bucket. Coarse, and intentionally so:
        # a per-IP bucket is a per-attacker bucket when the attacker has a
        # /64, and the honest answer is that unauthenticated AI is a small
        # shared allowance.
        identity = str(user_id) if user_id else "anon"
        key = f"ai:budget:{feature.value}:{period.value}:{suffix}:{identity}"

        try:
            pipeline = self.client.pipeline()
            pipeline.incr(key)
            pipeline.expire(key, _TTL_SECONDS)
            used = int((await pipeline.execute())[0])
        except Exception as exc:
            # Fail closed. See the module docstring.
            logger.error("ai_budget_check_failed", feature=feature.value, error=str(exc)[:200])
            raise errors.ModelUnavailableError("The assistant is temporarily unavailable.") from exc

        if used > limit:
            logger.info(
                "ai_budget_exceeded",
                feature=feature.value,
                identity=identity,
                used=used,
                limit=limit,
            )
            raise errors.AIBudgetExceededError(feature.value, resets_in)


@dataclass(slots=True)
class UnlimitedBudget:
    """For tests and for the worker.

    Background analysis is driven by our own events at a rate we control, so
    there is no user to meter — and metering it against the *guest* who
    triggered it would let one prolific reviewer exhaust their own chat
    allowance by writing reviews.
    """

    async def consume(
        self, *, user_id: uuid.UUID | None, feature: Feature, limit: int, period: Period
    ) -> None:
        return None
