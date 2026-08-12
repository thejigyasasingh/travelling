"""Recommendations.

The shape of every use case here is the same and it is the important part:

    retrieve (SQL)  →  rank (arithmetic)  →  explain (model, optional)

The first two steps are the product. The third is a sentence. If the model is
disabled, down, slow, or returns nonsense, the guest still gets the same
properties in the same order — they just do not get the "because …" line. That
is a degradation nobody files a bug about, which is the standard an optional
dependency has to meet before it goes in a page that must render.

The inversion — model picks, SQL explains — is what most implementations do and
it fails in three ways at once: it cannot be reproduced, it can be manipulated
by the vendor-written text it reads, and it takes the page down when the
provider has a bad afternoon.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.modules.ai.application import prompts
from app.modules.ai.application.ports import CandidateSource, LanguageModel
from app.modules.ai.application.prompts import dumps
from app.modules.ai.domain import errors
from app.modules.ai.domain.grounding import fence, make_refs
from app.modules.ai.domain.ranking import diversify, score_candidates
from app.modules.ai.domain.value_objects import (
    Candidate,
    Recommendation,
    RecommendationSource,
)
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

#: Retrieve more than we return. Ranking needs something to choose between,
#: and diversification needs slack to drop from.
RETRIEVE_MULTIPLIER = 4
MAX_RETRIEVE = 60

#: Only the top few get an explanation. The sentence is worth paying for on the
#: results a guest actually reads, and the cost is linear in candidates.
EXPLAIN_TOP_N = 6


def _to_prompt_row(ref: str, candidate: Candidate) -> dict[str, Any]:
    """What the model is told about a candidate.

    Note what is absent: the price. The model has no legitimate use for it —
    it is forbidden from mentioning money — and a number in the prompt is a
    number that eventually appears in the output. Amenities are capped at eight
    because a resort listing forty of them crowds out every other candidate in
    the context.
    """
    row: dict[str, Any] = {
        "ref": ref,
        "name": candidate.name,
        "city": candidate.city,
        "type": candidate.property_type,
        "amenities": sorted(candidate.amenity_codes)[:8],
    }
    # Withheld below the confidence threshold rather than sent with a caveat.
    # A model told "rating 5.0 (1 review)" writes "highly rated" regardless.
    if candidate.is_rated:
        row["rating"] = round(candidate.review_average, 1)
        row["review_count"] = candidate.review_count
    if candidate.co_bookings:
        row["also_booked_by"] = candidate.co_bookings
    return row


@dataclass(slots=True)
class ExplainRecommendations:
    """Attach a one-line reason to each recommendation.

    Separated from the ranking use cases so every one of them gets the same
    treatment, and so the failure path is written once: **any** exception here
    logs and returns the input unchanged. There is no way for this to fail a
    request.
    """

    model: LanguageModel

    async def execute(
        self, recommendations: list[Recommendation], *, context: str
    ) -> list[Recommendation]:
        if not self.model.available or not recommendations:
            return recommendations

        head = recommendations[:EXPLAIN_TOP_N]
        catalogue = make_refs(head)
        rows = [_to_prompt_row(ref, rec.candidate) for ref, rec in catalogue.items()]

        try:
            result = await self.model.structured(
                system=prompts.REASON_SYSTEM,
                # The candidate names are vendor-written, so they are fenced
                # like any other untrusted text even though they sit inside a
                # JSON structure we built.
                user=f"CONTEXT: {context}\nCANDIDATES:\n"
                + fence("candidate_list", dumps(rows), limit=6_000),
                schema=prompts.REASON_SCHEMA,
                tool_name="write_reasons",
                fast=True,
            )
        except Exception as exc:
            # Deliberately broad. This is decoration on a page that must
            # render, and there is no failure mode here worth showing a guest.
            logger.warning("recommendation_reasons_failed", error=str(exc)[:200])
            return recommendations

        by_ref = {
            str(item.get("ref", "")).upper(): str(item.get("reason", "")).strip()
            for item in result.get("reasons", [])
            if isinstance(item, dict)
        }

        explained: list[Recommendation] = []
        for ref, recommendation in catalogue.items():
            reason = by_ref.get(ref) or None
            explained.append(
                Recommendation(
                    candidate=recommendation.candidate,
                    score=recommendation.score,
                    source=recommendation.source,
                    reason=reason,
                )
            )
        # Anything past the explained head keeps its place, without a reason.
        return explained + recommendations[EXPLAIN_TOP_N:]


@dataclass(slots=True)
class RecommendSimilar:
    """ "More like this", on a property page.

    Blends two retrievals. Co-booking is the stronger signal but is empty for
    any property nobody has booked yet — which is every new listing — so
    content similarity backfills it. Merging rather than choosing means a
    listing's first weeks are not a dead zone on every page that links to it.
    """

    candidates: CandidateSource
    explain: ExplainRecommendations

    async def execute(
        self, property_id: uuid.UUID, *, city: str = "", limit: int = 8
    ) -> list[Recommendation]:
        budget = min(limit * RETRIEVE_MULTIPLIER, MAX_RETRIEVE)
        behavioural = await self.candidates.also_booked(property_id, limit=budget)
        content = await self.candidates.similar_to(property_id, limit=budget)

        # Merge on id, preferring the behavioural row: it carries the
        # co-booking count, and the content row carries only distance. Taking
        # distance from the content row where both exist gives each candidate
        # both signals.
        merged: dict[uuid.UUID, Candidate] = {c.property_id: c for c in content}
        for candidate in behavioural:
            existing = merged.get(candidate.property_id)
            merged[candidate.property_id] = Candidate(
                property_id=candidate.property_id,
                name=candidate.name,
                city=candidate.city,
                property_type=candidate.property_type,
                min_rate_minor=candidate.min_rate_minor,
                currency=candidate.currency,
                review_average=candidate.review_average,
                review_count=candidate.review_count,
                amenity_codes=candidate.amenity_codes,
                distance_km=existing.distance_km if existing else None,
                co_bookings=candidate.co_bookings,
            )

        if not merged:
            # Neither signal found anything. Common, and not an error: a listing
            # nobody has booked yet, in a price band nothing else in the city
            # occupies. An empty "more like this" rail is a worse answer than an
            # honest one, so fall back to the city — labelled NEARBY rather than
            # SIMILAR, because these are not similar and saying so is the
            # difference between a useful rail and a misleading one.
            fallback_city = city or await self.candidates.city_of(property_id)
            nearby = await self.candidates.popular_in(fallback_city, limit=budget)
            ranked = score_candidates(
                list(nearby),
                source=RecommendationSource.NEARBY,
                exclude=[property_id],
                limit=limit,
            )
            return await self.explain.execute(
                ranked, context="other places in the same city, because nothing closely matches"
            )

        source = RecommendationSource.ALSO_BOOKED if behavioural else RecommendationSource.SIMILAR
        ranked = score_candidates(
            list(merged.values()),
            source=source,
            exclude=[property_id],
            limit=limit,
        )
        return await self.explain.execute(ranked, context="shown alongside a property being viewed")


@dataclass(slots=True)
class RecommendForYou:
    """The personalised feed.

    Falls back through three tiers, and says which one it used. A first-time
    visitor gets popularity labelled as popularity — a "picked for you" rail
    that is really a top-ten list is a small lie that gets found out the first
    time two people compare screens.
    """

    candidates: CandidateSource
    explain: ExplainRecommendations

    async def execute(
        self, actor: Actor, *, city: str = "", limit: int = 12
    ) -> list[Recommendation]:
        budget = min(limit * RETRIEVE_MULTIPLIER, MAX_RETRIEVE)

        if actor.user_id is not None:
            history = await self.candidates.from_history(actor.user_id, limit=budget)
            if history:
                ranked = score_candidates(
                    history, source=RecommendationSource.YOUR_HISTORY, limit=limit * 2
                )
                return await self.explain.execute(
                    diversify(ranked)[:limit], context="based on where this guest has stayed before"
                )

        popular = await self.candidates.popular_in(city, limit=budget)
        if not popular:
            raise errors.NothingToRecommendError(f"popular_in:{city or 'anywhere'}")

        ranked = score_candidates(popular, source=RecommendationSource.POPULAR, limit=limit * 2)
        return await self.explain.execute(
            diversify(ranked)[:limit], context="popular right now, for a first-time visitor"
        )


@dataclass(slots=True)
class SuggestDestinations:
    """Where to go next.

    The only use case where the model chooses rather than explains — and it
    chooses from a list of cities we have supply in, so the worst outcome is a
    poorly ordered set of places a guest can actually book.

    Falls back to the platform's busiest cities when the model is unavailable,
    which is a worse answer but a real one.
    """

    candidates: CandidateSource
    model: LanguageModel

    async def execute(self, actor: Actor, *, month: str, limit: int = 5) -> list[dict[str, Any]]:
        cities = await self.candidates.cities_with_supply()
        if not cities:
            raise errors.NothingToRecommendError("no_cities_with_supply")

        history: list[dict[str, Any]] = []
        if actor.user_id is not None:
            history = await self.candidates.stay_history(actor.user_id)

        if not self.model.available:
            return [{"city": city, "reason": None, "generic": True} for city in cities[:limit]]

        try:
            result = await self.model.structured(
                system=prompts.DESTINATION_SYSTEM,
                user=(
                    f"CURRENT MONTH: {month}\n"
                    f"CANDIDATES (cities with availability): {dumps(cities)}\n"
                    f"PAST STAYS:\n{fence('stay_history', dumps(history), limit=1_000)}"
                ),
                schema=prompts.DESTINATION_SCHEMA,
                tool_name="suggest_destinations",
            )
        except Exception as exc:
            logger.warning("destination_suggestions_failed", error=str(exc)[:200])
            return [{"city": city, "reason": None, "generic": True} for city in cities[:limit]]

        # Grounding, again by whitelist rather than by trust: a city the model
        # invented is a city we cannot sell, and a guest who follows it lands
        # on an empty search.
        allowed = {city.casefold(): city for city in cities}
        generic = bool(result.get("generic", False))
        suggestions: list[dict[str, Any]] = []
        dropped: list[str] = []

        for item in result.get("suggestions", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("city", "")).strip()
            canonical = allowed.get(name.casefold())
            if canonical is None:
                dropped.append(name[:40])
                continue
            suggestions.append(
                {
                    "city": canonical,
                    "reason": str(item.get("reason", "")).strip() or None,
                    "best_months": [str(m)[:12] for m in item.get("best_months", [])][:12],
                    "generic": generic,
                }
            )

        if dropped:
            logger.warning("destinations_off_catalogue", dropped=dropped, offered=len(cities))
        if not suggestions:
            return [{"city": city, "reason": None, "generic": True} for city in cities[:limit]]
        return suggestions[:limit]
