"""The shapes the AI module reasons about."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Final

from app.modules.ai.domain import errors

# ══════════════════════════════════════════════════════════════════════════
# Sentiment
# ══════════════════════════════════════════════════════════════════════════


class Sentiment(StrEnum):
    POSITIVE = "positive"
    MIXED = "mixed"
    NEGATIVE = "negative"


#: The aspects a stay is judged on. Fixed rather than free-form: a model left
#: to invent aspect names produces "cleanliness", "clean", "hygiene" and
#: "tidiness" across four reviews of the same property, and none of them
#: aggregate. A closed set is the difference between a chart and a word cloud.
ASPECTS: Final = (
    "cleanliness",
    "location",
    "value",
    "service",
    "comfort",
    "food",
    "facilities",
    "noise",
    "accuracy",
)


@dataclass(frozen=True, slots=True)
class AspectScore:
    """What one review said about one aspect.

    ``score`` is -1, 0 or +1 rather than a scale. A model asked for a number
    out of ten produces a distribution that shifts between model versions and
    cannot be compared across a year of reviews; a sign is stable.
    """

    aspect: str
    score: int
    #: The guest's own words, quoted back. Verbatim so a host can see what was
    #: actually said rather than the model's paraphrase of it — and because a
    #: paraphrase presented as a quotation is a fabrication.
    quote: str | None = None

    def __post_init__(self) -> None:
        if self.aspect not in ASPECTS:
            raise errors.UnknownAspectError(self.aspect)
        if self.score not in (-1, 0, 1):
            raise errors.InvalidAspectScoreError(self.score)


@dataclass(frozen=True, slots=True)
class ReviewInsight:
    """The analysis of a single review."""

    sentiment: Sentiment
    aspects: tuple[AspectScore, ...]
    summary: str
    #: Raised when a review describes something a human should see quickly — a
    #: safety problem, a discrimination complaint, a claim of being charged
    #: twice. It routes to support; it does **not** hide the review.
    needs_attention: bool = False
    attention_reason: str | None = None

    @property
    def positives(self) -> tuple[str, ...]:
        return tuple(a.aspect for a in self.aspects if a.score > 0)

    @property
    def negatives(self) -> tuple[str, ...]:
        return tuple(a.aspect for a in self.aspects if a.score < 0)


# ══════════════════════════════════════════════════════════════════════════
# Recommendations
# ══════════════════════════════════════════════════════════════════════════


class RecommendationSource(StrEnum):
    """Why a property was put in front of someone.

    Carried through to the response and rendered as the "because …" line. Not
    decoration: a recommendation a guest cannot account for is one they assume
    was paid for, and the assumption is usually right elsewhere.
    """

    #: Guests who booked the property you are looking at also booked this one.
    ALSO_BOOKED = "also_booked"
    #: Similar attributes — type, price band, amenities, neighbourhood.
    SIMILAR = "similar"
    #: Drawn from where this guest has stayed before.
    YOUR_HISTORY = "your_history"
    #: Popular in this city right now. The cold-start answer, and honest about
    #: being one.
    POPULAR = "popular"
    #: Near the place being viewed.
    NEARBY = "nearby"


@dataclass(frozen=True, slots=True)
class Candidate:
    """A property that survived retrieval, before ranking.

    Deliberately flat and read-only: this crosses into prompt text, and an
    aggregate with behaviour on it would eventually have something private
    serialised into a request to a third party.
    """

    property_id: uuid.UUID
    name: str
    city: str
    property_type: str
    min_rate_minor: int | None
    currency: str
    review_average: float
    review_count: int
    amenity_codes: frozenset[str]
    #: Kilometres from the anchor property, when there is one.
    distance_km: float | None = None
    #: How many guests booked both this and the anchor.
    co_bookings: int = 0

    @property
    def is_rated(self) -> bool:
        """Fewer than three reviews is not a rating, it is an anecdote."""
        return self.review_count >= 3


@dataclass(frozen=True, slots=True)
class Recommendation:
    """A ranked candidate, with the reason it was chosen."""

    candidate: Candidate
    score: float
    source: RecommendationSource
    #: One sentence, model-written, grounded in the candidate's own attributes.
    #: ``None`` whenever the model is unavailable or disabled — the
    #: recommendation still stands, it just does not explain itself.
    reason: str | None = None


# ══════════════════════════════════════════════════════════════════════════
# Itineraries
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class ItineraryItem:
    """One thing to do, at one time of day."""

    time_of_day: str
    title: str
    description: str
    #: Set only when the item refers to a property in our catalogue. Everything
    #: else — a beach, a market, a restaurant — carries no id and is presented
    #: as a suggestion rather than as something bookable.
    property_id: uuid.UUID | None = None
    duration_minutes: int | None = None


@dataclass(frozen=True, slots=True)
class ItineraryDay:
    day: int
    date: date | None
    title: str
    items: tuple[ItineraryItem, ...]
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ItineraryPlan:
    city: str
    days: tuple[ItineraryDay, ...]
    summary: str
    #: Properties from our catalogue that the plan actually referenced, in the
    #: order they appear. Resolved from references, so a hallucinated hotel
    #: cannot reach the response.
    referenced_property_ids: tuple[uuid.UUID, ...] = ()
    #: The model's own admission that it does not know the city well. Carried
    #: through to the response and rendered as a caveat rather than dropped —
    #: a plan presented with false confidence is worse than one that says it
    #: is a starting point.
    low_confidence: bool = False


# ══════════════════════════════════════════════════════════════════════════
# Image tagging
# ══════════════════════════════════════════════════════════════════════════


class TagKind(StrEnum):
    #: Maps to an amenity code in the catalogue, so it can drive search.
    AMENITY = "amenity"
    #: What the photograph is of: bedroom, pool, exterior.
    SCENE = "scene"
    #: Free-form descriptive, for alt text and nothing else.
    DESCRIPTIVE = "descriptive"


@dataclass(frozen=True, slots=True)
class ImageTag:
    label: str
    kind: TagKind
    confidence: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise errors.InvalidConfidenceError(self.confidence)


@dataclass(frozen=True, slots=True)
class ImageAnnotation:
    """What a vision model saw in one photograph.

    ``alt_text`` is the part that matters most and the part nobody asks for:
    every property image on the platform currently ships without one, which
    makes the whole catalogue unusable with a screen reader.
    """

    tags: tuple[ImageTag, ...]
    alt_text: str
    #: Amenity codes the image supports, already intersected with the real
    #: catalogue. A vision model that sees a hot tub in a photograph is
    #: evidence, not authority: these are suggestions for the host to confirm,
    #: never applied to a listing automatically.
    suggested_amenities: frozenset[str] = field(default_factory=frozenset)
    #: Set when the image should not be published — a person's face, a document,
    #: something explicit. Reviewed by a human; never auto-deleted.
    flagged: bool = False
    flag_reason: str | None = None
