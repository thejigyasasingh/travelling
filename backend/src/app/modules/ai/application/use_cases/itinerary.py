"""The itinerary generator.

The expensive call in the module, so most of this file is about not making it.
Itineraries are cached on *what was asked* rather than on who asked, which
means two guests planning four days in Goa for a couple share one generation.
That only holds because the request carries nothing personal — see
:meth:`GenerateItinerary._cache_key` — and it is the reason the request schema
has no free-text "tell us about yourself" field.

The grounding rule here is narrower than elsewhere and worth stating: the model
may attach a property reference only to an item where *staying somewhere* is
the point. A beach with a property id would render as a bookable link to a
beach.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.clock import Clock
from app.core.logging import get_logger
from app.modules.ai.application import prompts
from app.modules.ai.application.ports import CandidateSource, LanguageModel
from app.modules.ai.application.prompts import dumps
from app.modules.ai.domain import errors
from app.modules.ai.domain.grounding import fence, make_refs, sanitise
from app.modules.ai.domain.value_objects import (
    Candidate,
    ItineraryDay,
    ItineraryItem,
    ItineraryPlan,
)

logger = get_logger(__name__)

MAX_DAYS = 21
#: Enough for the model to have real choices without paying for a context full
#: of properties it will never mention.
GROUNDING_CANDIDATES = 12
#: The one free-text field. Short enough that it cannot carry an instruction
#: frame, long enough for "travelling with a toddler, no long drives".
MAX_INTERESTS_CHARS = 300


@dataclass(frozen=True, slots=True)
class ItineraryRequest:
    city: str
    days: int
    travellers: str = "any"
    interests: str = ""

    def normalised(self) -> dict[str, Any]:
        """The canonical form, for hashing.

        Case and whitespace are flattened so "Goa" and " goa " are one cache
        entry rather than two generations.
        """
        return {
            "city": self.city.strip().casefold(),
            "days": self.days,
            "travellers": self.travellers.strip().casefold(),
            "interests": " ".join(self.interests.split()).casefold()[:MAX_INTERESTS_CHARS],
        }


def _prompt_row(ref: str, candidate: Candidate) -> dict[str, Any]:
    return {
        "ref": ref,
        "name": candidate.name,
        "type": candidate.property_type,
        "amenities": sorted(candidate.amenity_codes)[:6],
    }


@dataclass(slots=True)
class GenerateItinerary:
    """Produce, or reuse, a day-by-day plan."""

    candidates: CandidateSource
    model: LanguageModel
    clock: Clock
    cache_days: int = 14

    @staticmethod
    def _cache_key(request: ItineraryRequest) -> str:
        """SHA-256 over the normalised request.

        Nothing about the requester participates. If a user id ever finds its
        way in here, the cache stops working *and* starts storing a profile —
        both bad, in that order of how quickly you notice.
        """
        return hashlib.sha256(dumps(request.normalised()).encode()).hexdigest()

    async def execute(
        self, request: ItineraryRequest, *, cached: dict[str, Any] | None = None
    ) -> tuple[ItineraryPlan, str, bool]:
        """Returns the plan, its cache key, and whether it was generated now."""
        if not 1 <= request.days <= MAX_DAYS:
            raise errors.ModelResponseInvalidError(f"days must be 1..{MAX_DAYS}")

        key = self._cache_key(request)
        if cached is not None:
            return self._from_cache(cached, city=request.city), key, False

        if not self.model.available:
            raise errors.ModelUnavailableError(
                "Itinerary planning is unavailable right now. Search still works."
            )

        pool = await self.candidates.in_city(request.city, limit=GROUNDING_CANDIDATES)
        catalogue = make_refs(list(pool))

        result = await self.model.structured(
            system=prompts.ITINERARY_SYSTEM,
            user=(
                f"CITY: {sanitise(request.city, limit=120)}\n"
                f"DAYS: {request.days}\n"
                f"TRAVELLERS: {sanitise(request.travellers, limit=60)}\n"
                "INTERESTS:\n"
                + fence("guest_interests", request.interests, limit=MAX_INTERESTS_CHARS)
                + "\n"
                "CANDIDATES:\n"
                + fence(
                    "candidate_list",
                    dumps([_prompt_row(r, c) for r, c in catalogue.items()]),
                    limit=4_000,
                )
            ),
            schema=prompts.ITINERARY_SCHEMA,
            tool_name="build_itinerary",
        )

        plan = self._parse(result, request=request, catalogue=catalogue)
        return plan, key, True

    # ── parsing ───────────────────────────────────────────────────────────

    def _parse(
        self,
        result: dict[str, Any],
        *,
        request: ItineraryRequest,
        catalogue: dict[str, Candidate],
    ) -> ItineraryPlan:
        referenced: list[uuid.UUID] = []
        days: list[ItineraryDay] = []
        invented: list[str] = []

        for raw_day in result.get("days", [])[:MAX_DAYS]:
            if not isinstance(raw_day, dict):
                continue
            items: list[ItineraryItem] = []
            for raw_item in raw_day.get("items", []):
                if not isinstance(raw_item, dict):
                    continue

                property_id: uuid.UUID | None = None
                ref = str(raw_item.get("property_ref", "")).strip().upper()
                if ref:
                    candidate = catalogue.get(ref)
                    if candidate is None:
                        # Dropped, not raised: an otherwise good five-day plan
                        # should not be discarded because one item cited a
                        # hotel that does not exist. The item survives as a
                        # suggestion with no link.
                        invented.append(ref[:10])
                    else:
                        property_id = candidate.property_id
                        if property_id not in referenced:
                            referenced.append(property_id)

                items.append(
                    ItineraryItem(
                        time_of_day=str(raw_item.get("time_of_day", "")),
                        title=str(raw_item.get("title", "")).strip(),
                        description=str(raw_item.get("description", "")).strip(),
                        property_id=property_id,
                        duration_minutes=raw_item.get("duration_minutes"),
                    )
                )

            if not items:
                continue
            days.append(
                ItineraryDay(
                    day=int(raw_day.get("day", len(days) + 1)),
                    date=None,
                    title=str(raw_day.get("title", "")).strip(),
                    items=tuple(items),
                    note=(str(raw_day["note"]).strip() if raw_day.get("note") else None),
                )
            )

        if invented:
            logger.warning(
                "itinerary_referenced_unknown_property",
                refs=invented,
                offered=len(catalogue),
                city=request.city,
            )
        if not days:
            raise errors.ModelResponseInvalidError("itinerary contained no usable days")

        return ItineraryPlan(
            city=request.city,
            days=tuple(days),
            summary=str(result.get("summary", "")).strip(),
            referenced_property_ids=tuple(referenced),
            low_confidence=bool(result.get("low_confidence", False)),
        )

    def _from_cache(self, stored: dict[str, Any], *, city: str) -> ItineraryPlan:
        """Rebuild a plan from the stored JSON.

        Property ids are read back as-is. They were validated against the
        catalogue when the plan was generated, and a listing unpublished since
        then is handled by invalidating on that event rather than by
        re-checking on every read — the alternative is a query per cached
        itinerary served.
        """
        days = tuple(
            ItineraryDay(
                day=int(day["day"]),
                date=None,
                title=str(day.get("title", "")),
                note=day.get("note"),
                items=tuple(
                    ItineraryItem(
                        time_of_day=str(item.get("time_of_day", "")),
                        title=str(item.get("title", "")),
                        description=str(item.get("description", "")),
                        property_id=(
                            uuid.UUID(item["property_id"]) if item.get("property_id") else None
                        ),
                        duration_minutes=item.get("duration_minutes"),
                    )
                    for item in day.get("items", [])
                ),
            )
            for day in stored.get("days", [])
        )
        return ItineraryPlan(
            city=city,
            days=days,
            summary=str(stored.get("summary", "")),
            referenced_property_ids=tuple(
                uuid.UUID(pid) for pid in stored.get("referenced_property_ids", [])
            ),
            low_confidence=bool(stored.get("low_confidence", False)),
        )

    def expires_at(self) -> datetime:
        now = self.clock.now() if hasattr(self.clock, "now") else datetime.now(UTC)
        return now + timedelta(days=self.cache_days)


def plan_to_json(plan: ItineraryPlan) -> dict[str, Any]:
    """Serialise for storage. Mirrors :meth:`GenerateItinerary._from_cache`."""
    return {
        "summary": plan.summary,
        "low_confidence": plan.low_confidence,
        "referenced_property_ids": [str(pid) for pid in plan.referenced_property_ids],
        "days": [
            {
                "day": day.day,
                "title": day.title,
                "note": day.note,
                "items": [
                    {
                        "time_of_day": item.time_of_day,
                        "title": item.title,
                        "description": item.description,
                        "property_id": str(item.property_id) if item.property_id else None,
                        "duration_minutes": item.duration_minutes,
                    }
                    for item in day.items
                ],
            }
            for day in plan.days
        ],
    }
