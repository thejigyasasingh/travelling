"""Search.

Thin on purpose. The interesting work is one SQL statement in
``infrastructure/search_repository.py``; this layer validates the request,
decides caching, and keeps a bad query from reaching the database.

**Caching.** Search is the highest-volume endpoint and its results change
slowly — a listing's rates and availability move a few times a day, not a few
times a second. Results are cached for a short TTL keyed on the *whole*
criteria set, with stampede protection, so a homepage spike hits Postgres once
rather than ten thousand times.

Anything with dates is cached for a much shorter window, because availability
is the fastest-moving input and a stale "available" produces a booking that
cannot be honoured.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Final

import orjson

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.serialization import dto_dict
from app.core.types.pagination import Cursor, InvalidCursorError
from app.infrastructure.cache.cache import RedisCache, cache_key
from app.modules.property.application.dto import (
    SearchCriteria,
    SearchResultItem,
    SearchResults,
)
from app.modules.property.application.ports import SearchRepository
from app.modules.property.domain import errors
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

#: Availability moves fastest, so date-bearing searches get the shortest life.
CACHE_TTL_WITH_DATES: Final = timedelta(seconds=60)
CACHE_TTL_BROWSE: Final = timedelta(minutes=5)

#: The furthest ahead a guest may search. Past this, rates are guesses and the
#: cancellation rate is high enough that the booking is worth less than the
#: inventory it holds.
MAX_SEARCH_HORIZON_DAYS: Final = 550
MAX_STAY_NIGHTS: Final = 90
MAX_ROOMS_PER_SEARCH: Final = 8


@dataclass(slots=True)
class SearchPropertiesUseCase:
    search: SearchRepository
    cache: RedisCache
    clock: Clock

    async def execute(self, criteria: SearchCriteria, actor: Actor) -> SearchResults:
        self._validate(criteria)

        # Vendor-scoped searches are never cached: the vendor is looking at
        # their own inventory and has just edited it, so a 60-second-stale
        # answer reads as "my change did not save".
        if criteria.include_unpublished or criteria.vendor_id is not None:
            return await self.search.search(criteria)

        key = cache_key("search", self._fingerprint(criteria))
        ttl = CACHE_TTL_WITH_DATES if criteria.has_dates else CACHE_TTL_BROWSE

        payload = await self.cache.get_or_set(
            key, lambda: self._run(criteria), ttl, lock_timeout=2.0
        )
        return _decode(payload)

    async def _run(self, criteria: SearchCriteria) -> dict[str, Any]:
        results = await self.search.search(criteria)
        logger.info(
            "search_executed",
            has_dates=criteria.has_dates,
            has_location=criteria.near is not None or criteria.bounds is not None,
            filters=len(criteria.amenity_codes) + len(criteria.property_types),
            sort=criteria.sort.value,
            results=len(results.items),
        )
        return _encode(results)

    def _validate(self, criteria: SearchCriteria) -> None:
        today = self.clock.now().date()

        if criteria.stay is not None:
            self._validate_stay(criteria.stay.start, criteria.stay.end, today)

        if criteria.rooms < 1 or criteria.rooms > MAX_ROOMS_PER_SEARCH:
            msg = f"rooms must be between 1 and {MAX_ROOMS_PER_SEARCH}"
            raise errors.SearchWindowError(msg)

        if (
            criteria.min_price_minor is not None
            and criteria.max_price_minor is not None
            and criteria.min_price_minor > criteria.max_price_minor
        ):
            msg = "min_price cannot exceed max_price"
            raise errors.SearchWindowError(msg)

        if criteria.bounds is not None:
            sw, ne = criteria.bounds
            if sw.latitude >= ne.latitude:
                # Longitude may legitimately wrap across the antimeridian;
                # latitude never can.
                msg = "The south-west corner must be south of the north-east corner"
                raise errors.SearchWindowError(msg)

    @staticmethod
    def _validate_stay(check_in: date, check_out: date, today: date) -> None:
        if check_in < today:
            msg = "Check-in cannot be in the past"
            raise errors.SearchWindowError(msg, check_in=str(check_in))
        if check_out <= check_in:
            msg = "Check-out must be after check-in"
            raise errors.SearchWindowError(msg)
        if (check_out - check_in).days > MAX_STAY_NIGHTS:
            msg = f"A stay may not exceed {MAX_STAY_NIGHTS} nights"
            raise errors.SearchWindowError(msg, max_nights=MAX_STAY_NIGHTS)
        if (check_in - today).days > MAX_SEARCH_HORIZON_DAYS:
            msg = f"Bookings open {MAX_SEARCH_HORIZON_DAYS} days ahead"
            raise errors.SearchWindowError(msg, max_days=MAX_SEARCH_HORIZON_DAYS)

    @staticmethod
    def _fingerprint(criteria: SearchCriteria) -> str:
        """A stable cache key for the whole criteria set.

        Sorted and canonical, so ``{pool, wifi}`` and ``{wifi, pool}`` are one
        cache entry rather than two. Coordinates are rounded to ~100 m: a map
        that moves a few metres between renders must not miss the cache on
        every frame.
        """
        parts = {
            "q": (criteria.query or "").strip().lower(),
            "city": str(criteria.city_id) if criteria.city_id else None,
            "near": (
                [round(criteria.near.latitude, 3), round(criteria.near.longitude, 3)]
                if criteria.near
                else None
            ),
            "r": criteria.effective_radius_m if criteria.near else None,
            "bounds": (
                [
                    round(criteria.bounds[0].latitude, 3),
                    round(criteria.bounds[0].longitude, 3),
                    round(criteria.bounds[1].latitude, 3),
                    round(criteria.bounds[1].longitude, 3),
                ]
                if criteria.bounds
                else None
            ),
            "stay": (
                [criteria.stay.start.isoformat(), criteria.stay.end.isoformat()]
                if criteria.stay
                else None
            ),
            "occ": [
                criteria.occupancy.adults,
                criteria.occupancy.children,
                criteria.occupancy.infants,
            ],
            "rooms": criteria.rooms,
            "types": sorted(t.value for t in criteria.property_types),
            "amen": sorted(criteria.amenity_codes),
            "price": [criteria.min_price_minor, criteria.max_price_minor],
            "rating": str(criteria.min_rating) if criteria.min_rating else None,
            "instant": criteria.instant_booking_only,
            "cancel": sorted(p.value for p in criteria.cancellation_policies),
            "sort": criteria.sort.value,
            "limit": criteria.limit,
            "cursor": criteria.cursor.encode() if criteria.cursor else None,
        }
        raw = orjson.dumps(parts, option=orjson.OPT_SORT_KEYS)
        return hashlib.sha256(raw).hexdigest()[:32]


@dataclass(slots=True)
class SuggestUseCase:
    """Type-ahead for the search box.

    Never cached in Redis per prefix — the key space is every prefix anyone has
    ever typed, which fills memory with entries used once. The underlying
    trigram index is fast enough on its own.
    """

    search: SearchRepository

    async def execute(self, prefix: str, actor: Actor) -> list[dict[str, Any]]:
        cleaned = prefix.strip()
        if len(cleaned) < 2:
            # One character matches most of the database and is never a real
            # intent — the user is still typing.
            return []
        return await self.search.suggest(cleaned[:80])


# ══════════════════════════════════════════════════════════════════════════
# Cache serialisation
#
# Results are cached as plain dicts, not pickled objects. Pickle in a cache is
# remote code execution for anyone who can write to Redis, and a pickled
# dataclass breaks on the next deploy that changes a field.
# ══════════════════════════════════════════════════════════════════════════


def _encode(results: SearchResults) -> dict[str, Any]:
    return {
        "items": [dto_dict(item) | {"id": str(item.id)} for item in results.items],
        "next_cursor": results.next_cursor,
        "total_estimate": results.total_estimate,
        "applied_radius_m": results.applied_radius_m,
    }


def _decode(payload: dict[str, Any]) -> SearchResults:
    import uuid

    return SearchResults(
        items=[
            SearchResultItem(**(item | {"id": uuid.UUID(item["id"])})) for item in payload["items"]
        ],
        next_cursor=payload.get("next_cursor"),
        total_estimate=payload.get("total_estimate"),
        applied_radius_m=payload.get("applied_radius_m"),
    )


def decode_cursor(raw: str | None) -> Cursor | None:
    """Surface a malformed cursor as a 422, never a 500.

    Clients send stale cursors constantly — a bookmarked URL, a back button —
    and none of those should page anyone.
    """
    if not raw:
        return None
    try:
        return Cursor.decode(raw)
    except InvalidCursorError:
        raise
