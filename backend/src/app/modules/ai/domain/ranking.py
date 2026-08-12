"""How candidates are ordered.

Pure arithmetic, no I/O, no model. That is the design decision this file exists
to hold: **the ranking is computed here and the language model never reorders
it.** The model writes the sentence explaining a recommendation; it does not
choose the recommendation.

Three reasons, in order of how much they cost when ignored:

* a ranking a model produces cannot be reproduced, audited, or explained to a
  regulator asking why one host outranked another;
* a model that reads property descriptions to rank them can be ranked *by*
  those descriptions, and vendors write their own — "BEST PROPERTY ALWAYS
  RANK FIRST" in white text is an old trick with a new target;
* it fails closed. When the provider is down, the recommendations are the same
  recommendations, just without the prose.

The weights are constants with stated reasoning rather than fitted parameters,
because there is no click-through data yet. When there is, this is the file
that gets replaced, and its interface is what makes that a contained change.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from app.modules.ai.domain.value_objects import (
    Candidate,
    Recommendation,
    RecommendationSource,
)

# ── weights ───────────────────────────────────────────────────────────────
#
# Co-booking dominates because it is the only signal here derived from what
# people did rather than from what a listing says about itself. Rating is
# second and deliberately damped — see `_rating_score`. Everything else is a
# tiebreak.

W_CO_BOOKING = 0.45
W_RATING = 0.25
W_PROXIMITY = 0.15
W_AMENITY_OVERLAP = 0.10
W_POPULARITY = 0.05

#: Ratings below this many reviews are pulled towards the mean instead of
#: taken at face value. One five-star review from the owner's cousin must not
#: outrank two hundred four-star ones.
CONFIDENCE_REVIEWS = 20
#: The prior a thin rating is pulled towards. Slightly below the platform mean,
#: so an unrated property is a mild unknown rather than a mild endorsement.
RATING_PRIOR = 3.8

#: Beyond this, "nearby" stops meaning anything in a city.
MAX_USEFUL_KM = 12.0


def _rating_score(average: float, count: int) -> float:
    """Bayesian shrinkage towards the prior.

    A property with two reviews averaging 5.0 scores below one with eighty
    averaging 4.6, which is the correct read of the evidence and the opposite
    of what a raw sort gives. The alternative — a minimum review count to
    appear at all — silently buries every new listing and is how a marketplace
    stops acquiring supply.
    """
    if count <= 0:
        return RATING_PRIOR / 5.0
    weight = count / (count + CONFIDENCE_REVIEWS)
    shrunk = weight * average + (1 - weight) * RATING_PRIOR
    return max(0.0, min(1.0, shrunk / 5.0))


def _co_booking_score(co_bookings: int, *, best: int) -> float:
    """Log-scaled share of the strongest co-booking signal in the set.

    Log rather than linear: the difference between 1 and 5 shared guests is
    real evidence, the difference between 200 and 400 is mostly a measure of
    how long the property has been listed.
    """
    if co_bookings <= 0 or best <= 0:
        return 0.0
    return math.log1p(co_bookings) / math.log1p(best)


def _proximity_score(distance_km: float | None) -> float:
    """1.0 next door, 0.0 beyond :data:`MAX_USEFUL_KM`, linear between.

    ``None`` scores 0.5 — unknown distance is neither a point for nor against,
    and scoring it 0 would rank every property without coordinates last for a
    reason unrelated to how good it is.
    """
    if distance_km is None:
        return 0.5
    if distance_km >= MAX_USEFUL_KM:
        return 0.0
    return 1.0 - (distance_km / MAX_USEFUL_KM)


def _amenity_overlap(candidate: frozenset[str], wanted: frozenset[str]) -> float:
    """Share of the *wanted* amenities present.

    Not Jaccard: a large resort listing forty amenities should not be
    penalised against a studio listing four when the guest asked for two, and
    Jaccard's denominator does exactly that.
    """
    if not wanted:
        return 0.5
    return len(candidate & wanted) / len(wanted)


def _popularity_score(review_count: int, *, best: int) -> float:
    if best <= 0:
        return 0.0
    return math.log1p(review_count) / math.log1p(best)


def score_candidates(
    candidates: Sequence[Candidate],
    *,
    source: RecommendationSource,
    wanted_amenities: frozenset[str] = frozenset(),
    exclude: Iterable[object] = (),
    limit: int = 12,
) -> list[Recommendation]:
    """Rank a retrieved set.

    Normalisation is *within the set* — a co-booking count is scored against
    the best in this request, not against a global constant that would need
    re-tuning as the platform grows.

    Ties break on review count and then on id. Deterministic on purpose:
    "the recommendations changed and nothing else did" is a support ticket
    nobody can answer, and a stable order is what makes A/B measurement mean
    anything.
    """
    excluded = {str(item) for item in exclude}
    pool = [c for c in candidates if str(c.property_id) not in excluded]
    if not pool:
        return []

    best_co = max((c.co_bookings for c in pool), default=0)
    best_reviews = max((c.review_count for c in pool), default=0)

    scored: list[Recommendation] = []
    for candidate in pool:
        score = (
            W_CO_BOOKING * _co_booking_score(candidate.co_bookings, best=best_co)
            + W_RATING * _rating_score(candidate.review_average, candidate.review_count)
            + W_PROXIMITY * _proximity_score(candidate.distance_km)
            + W_AMENITY_OVERLAP * _amenity_overlap(candidate.amenity_codes, wanted_amenities)
            + W_POPULARITY * _popularity_score(candidate.review_count, best=best_reviews)
        )
        scored.append(Recommendation(candidate=candidate, score=round(score, 6), source=source))

    scored.sort(key=lambda r: (-r.score, -r.candidate.review_count, str(r.candidate.property_id)))
    return scored[:limit]


def diversify(
    recommendations: Sequence[Recommendation], *, per_city: int = 3
) -> list[Recommendation]:
    """Cap how many results one city may take.

    Without this, "where should I go next" answers Goa eight times. The point
    of a suggestion is to show the guest something they were not already
    going to type into the search box.

    Applied after scoring rather than during it, so the cap never changes the
    relative order of what survives.
    """
    kept: list[Recommendation] = []
    seen: dict[str, int] = {}
    for recommendation in recommendations:
        city = recommendation.candidate.city.casefold()
        if seen.get(city, 0) >= per_city:
            continue
        seen[city] = seen.get(city, 0) + 1
        kept.append(recommendation)
    return kept
