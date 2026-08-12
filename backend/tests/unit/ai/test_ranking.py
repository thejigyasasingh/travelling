"""Recommendation ranking.

Every test here runs without a model, a database or a network, which is the
property being asserted as much as any individual number: **the ranking is
arithmetic.** If these tests ever need a fixture that talks to a provider,
something has been inverted and the recommendations have stopped being
reproducible.

The specific behaviours pinned below are the ones that go wrong quietly. A
ranking bug does not throw; it just puts the wrong hotel first, and nobody
notices until a host asks why they stopped appearing.
"""

from __future__ import annotations

import uuid

import pytest

from app.modules.ai.domain.ranking import (
    CONFIDENCE_REVIEWS,
    MAX_USEFUL_KM,
    RATING_PRIOR,
    _co_booking_score,
    _rating_score,
    diversify,
    score_candidates,
)
from app.modules.ai.domain.value_objects import (
    Candidate,
    Recommendation,
    RecommendationSource,
)

pytestmark = pytest.mark.unit


def candidate(
    *,
    name: str = "A House",
    city: str = "Panaji",
    rating: float = 4.5,
    reviews: int = 50,
    amenities: frozenset[str] = frozenset(),
    distance: float | None = None,
    co: int = 0,
) -> Candidate:
    return Candidate(
        property_id=uuid.uuid4(),
        name=name,
        city=city,
        property_type="villa",
        min_rate_minor=500_000,
        currency="INR",
        review_average=rating,
        review_count=reviews,
        amenity_codes=amenities,
        distance_km=distance,
        co_bookings=co,
    )


def scores(*candidates: Candidate, **kwargs: object) -> list[float]:
    ranked = score_candidates(
        list(candidates),
        source=RecommendationSource.SIMILAR,
        **kwargs,  # type: ignore[arg-type]
    )
    return [r.score for r in ranked]


# ══════════════════════════════════════════════════════════════════════════
# Rating confidence — the one people get wrong
# ══════════════════════════════════════════════════════════════════════════


def test_a_thin_five_star_loses_to_a_deep_four_six() -> None:
    """**The** rating rule.

    Two five-star reviews is not evidence of a better property than eighty
    averaging 4.6 — it is evidence of two reviews. A raw sort gets this exactly
    backwards, and the result is that every listing's first fortnight is spent
    at the top of the page.
    """
    thin = candidate(name="thin", rating=5.0, reviews=2)
    deep = candidate(name="deep", rating=4.6, reviews=80)

    ranked = score_candidates([thin, deep], source=RecommendationSource.SIMILAR)
    assert ranked[0].candidate.name == "deep"


def test_an_unrated_property_still_appears() -> None:
    """The opposite failure. A minimum review count to be recommended at all
    silently buries every new listing, which is how a marketplace stops
    acquiring supply."""
    new = candidate(name="new", rating=0.0, reviews=0)
    ranked = score_candidates([new], source=RecommendationSource.POPULAR)
    assert len(ranked) == 1
    assert ranked[0].score > 0


def test_an_unrated_property_scores_at_the_prior() -> None:
    """Not zero, not the mean. A listing nobody has reviewed is an unknown,
    and scoring it zero is a judgement nobody has earned.

    Asserted on the rating component directly rather than on the total. The
    total also carries a popularity term, which a property with no reviews
    correctly scores zero on — so comparing totals would be testing two
    things and pinning neither.
    """
    assert _rating_score(0.0, 0) == pytest.approx(RATING_PRIOR / 5.0)


def test_shrinkage_pulls_towards_the_prior_not_past_it() -> None:
    """A thin rating moves towards the prior; it never overshoots. Landing on
    the wrong side would make one glowing review score *worse* than none."""
    generous = _rating_score(5.0, 1)
    harsh = _rating_score(1.0, 1)
    prior = RATING_PRIOR / 5.0

    assert prior < generous < 1.0
    assert 0.0 < harsh < prior


def test_confidence_threshold_is_the_halfway_point() -> None:
    """At exactly `CONFIDENCE_REVIEWS`, the observed average and the prior
    carry equal weight. That is what the constant means, and it is easy to
    change the formula in a way that quietly moves it."""
    observed = 5.0
    halfway = _rating_score(observed, CONFIDENCE_REVIEWS)
    expected = (0.5 * observed + 0.5 * RATING_PRIOR) / 5.0
    assert halfway == pytest.approx(expected)


def test_confidence_grows_with_review_count() -> None:
    """More reviews at the same average is a stronger claim, so it must score
    higher — otherwise the shrinkage is doing nothing."""
    few = candidate(name="few", rating=4.9, reviews=5)
    many = candidate(name="many", rating=4.9, reviews=500)
    ranked = score_candidates([few, many], source=RecommendationSource.SIMILAR)
    assert ranked[0].candidate.name == "many"


# ══════════════════════════════════════════════════════════════════════════
# The other signals
# ══════════════════════════════════════════════════════════════════════════


def test_co_booking_outweighs_a_slightly_better_rating() -> None:
    """Co-booking is the only signal derived from what people did rather than
    from what a listing says about itself, which is why it carries the most
    weight."""
    behavioural = candidate(name="co", rating=4.2, reviews=40, co=30)
    rated = candidate(name="rated", rating=4.6, reviews=40, co=0)
    ranked = score_candidates([behavioural, rated], source=RecommendationSource.ALSO_BOOKED)
    assert ranked[0].candidate.name == "co"


def test_co_booking_is_log_scaled_not_linear() -> None:
    """1 → 5 shared guests is evidence; 200 → 400 mostly measures how long a
    listing has existed.

    Asserted against what linear scaling would give rather than against an
    arbitrary threshold: under linear, four extra guests out of four hundred
    is worth 1% of the range and is indistinguishable from noise. Under log it
    is worth a sixth of it.
    """
    top = 400
    log_share = _co_booking_score(5, best=top) - _co_booking_score(1, best=top)
    linear_share = (5 - 1) / top

    assert log_share > linear_share * 10, "the low end must be where the signal lives"
    assert _co_booking_score(top, best=top) == pytest.approx(1.0)
    assert _co_booking_score(0, best=top) == 0.0


def test_unknown_distance_is_neither_rewarded_nor_punished() -> None:
    """A property without coordinates would otherwise rank last for a reason
    unrelated to how good it is."""
    unknown = candidate(name="unknown", distance=None)
    far = candidate(name="far", distance=MAX_USEFUL_KM)
    near = candidate(name="near", distance=0.1)

    ranked = {r.candidate.name: r.score for r in scores_named(unknown, far, near)}
    assert ranked["near"] > ranked["unknown"] > ranked["far"]


def scores_named(*candidates: Candidate) -> list[Recommendation]:
    return score_candidates(list(candidates), source=RecommendationSource.SIMILAR)


def test_amenity_overlap_is_share_of_wanted_not_jaccard() -> None:
    """A resort listing forty amenities must not be penalised against a studio
    listing four when the guest asked for two. Jaccard's denominator does
    exactly that."""
    wanted = frozenset({"pool", "wifi"})
    small = candidate(name="small", amenities=frozenset({"pool", "wifi"}))
    large = candidate(
        name="large",
        amenities=frozenset({"pool", "wifi", *(f"x{i}" for i in range(38))}),
    )
    ranked = score_candidates(
        [small, large], source=RecommendationSource.SIMILAR, wanted_amenities=wanted
    )
    assert ranked[0].score == pytest.approx(ranked[1].score)


# ══════════════════════════════════════════════════════════════════════════
# Set behaviour
# ══════════════════════════════════════════════════════════════════════════


def test_the_anchor_property_is_excluded() -> None:
    """ "More like this" must not lead with the page you are already on."""
    anchor = candidate(name="anchor")
    other = candidate(name="other")
    ranked = score_candidates(
        [anchor, other], source=RecommendationSource.SIMILAR, exclude=[anchor.property_id]
    )
    assert [r.candidate.name for r in ranked] == ["other"]


def test_ordering_is_deterministic() -> None:
    """ "The recommendations changed and nothing else did" is a support ticket
    nobody can answer, and unstable order makes any A/B measurement
    meaningless."""
    pool = [candidate(name=f"p{i}", rating=4.5, reviews=50) for i in range(10)]
    first = [
        r.candidate.property_id for r in score_candidates(pool, source=RecommendationSource.SIMILAR)
    ]
    second = [
        r.candidate.property_id
        for r in score_candidates(list(reversed(pool)), source=RecommendationSource.SIMILAR)
    ]
    assert first == second


def test_limit_is_respected() -> None:
    pool = [candidate(name=f"p{i}") for i in range(30)]
    assert len(score_candidates(pool, source=RecommendationSource.POPULAR, limit=5)) == 5


def test_an_empty_pool_returns_empty() -> None:
    assert score_candidates([], source=RecommendationSource.POPULAR) == []


def test_excluding_everything_returns_empty_rather_than_raising() -> None:
    one = candidate()
    assert (
        score_candidates([one], source=RecommendationSource.SIMILAR, exclude=[one.property_id])
        == []
    )


# ══════════════════════════════════════════════════════════════════════════
# Diversification
# ══════════════════════════════════════════════════════════════════════════


def test_one_city_cannot_take_the_whole_list() -> None:
    """Without this, "where should I go next" answers Goa eight times — which
    is not a suggestion, it is the search box the guest already used."""
    pool = [candidate(name=f"goa{i}", city="Panaji") for i in range(8)]
    pool += [candidate(name="jaipur", city="Jaipur")]

    ranked = score_candidates(pool, source=RecommendationSource.POPULAR, limit=20)
    diverse = diversify(ranked, per_city=3)

    cities = [r.candidate.city for r in diverse]
    assert cities.count("Panaji") == 3
    assert "Jaipur" in cities


def test_diversify_preserves_relative_order() -> None:
    """The cap drops entries; it must not reorder the ones that survive, or
    the ranking and the displayed list stop agreeing."""
    pool = [candidate(name=f"p{i}", city=f"city{i % 2}", reviews=100 - i) for i in range(6)]
    ranked = score_candidates(pool, source=RecommendationSource.POPULAR, limit=20)
    diverse = diversify(ranked, per_city=2)
    assert [r.score for r in diverse] == sorted((r.score for r in diverse), reverse=True)


def test_city_matching_is_case_insensitive() -> None:
    """ "Panaji" and "panaji" are one city. Treating them as two defeats the
    cap with a data-entry difference."""
    pool = [
        candidate(name="a", city="Panaji"),
        candidate(name="b", city="panaji"),
        candidate(name="c", city="PANAJI"),
    ]
    ranked = score_candidates(pool, source=RecommendationSource.POPULAR)
    assert len(diversify(ranked, per_city=2)) == 2
