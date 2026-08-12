"""Review sentiment, and image tagging.

Both run **off the request path**, driven by domain events through the outbox.
A guest pressing "post review" must not wait on a model call, and a model
outage must not stop them reviewing. The consequence is that both handlers have
to be idempotent, because the outbox delivers at least once.

Idempotency here is a content hash, not a "have I seen this id" check. The
difference matters: an id check makes a *redelivery* free but leaves an *edited*
review with stale analysis forever. Hashing the analysed text gets both — a
redelivery matches and is skipped, an edit does not match and is redone.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.modules.ai.application import prompts
from app.modules.ai.application.ports import LanguageModel
from app.modules.ai.domain import errors
from app.modules.ai.domain.grounding import fence
from app.modules.ai.domain.value_objects import (
    ASPECTS,
    AspectScore,
    ImageAnnotation,
    ImageTag,
    ReviewInsight,
    Sentiment,
    TagKind,
)

logger = get_logger(__name__)

MAX_REVIEW_CHARS = 4_000
#: Below this the model is guessing from the image rather than reading it, and
#: a low-confidence amenity suggestion wastes a host's attention.
AMENITY_CONFIDENCE_FLOOR = 0.7


def content_hash(*parts: str) -> str:
    """Stable across processes and restarts.

    Explicitly *not* Python's ``hash()``, which is salted per process and would
    make every worker disagree about whether a review had already been
    analysed.
    """
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")  # so ("ab","c") and ("a","bc") differ
    return digest.hexdigest()


# ══════════════════════════════════════════════════════════════════════════
# Review sentiment
# ══════════════════════════════════════════════════════════════════════════


@dataclass(slots=True)
class AnalyseReview:
    """Turn one review into structured insight."""

    model: LanguageModel

    async def execute(self, *, title: str | None, body: str, rating: int) -> ReviewInsight:
        if not self.model.available:
            raise errors.ModelUnavailableError

        result = await self.model.structured(
            system=prompts.SENTIMENT_SYSTEM,
            # The star rating is supplied as context but the prompt forbids
            # inferring aspects from it. Without the rating the model reads
            # sarcasm as praise; with it as the only signal, every 5★ review
            # comes back "positive on everything".
            user=(
                f"STAR RATING: {rating}/5\n"
                f"TITLE:\n{fence('review_title', title or '', limit=200)}\n"
                f"BODY:\n{fence('review_body', body, limit=MAX_REVIEW_CHARS)}"
            ),
            schema=prompts.SENTIMENT_SCHEMA,
            tool_name="analyse_review",
            fast=True,
        )
        return self._parse(result)

    @staticmethod
    def _parse(result: dict[str, Any]) -> ReviewInsight:
        aspects: list[AspectScore] = []
        seen: set[str] = set()

        for raw in result.get("aspects", []):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("aspect", ""))
            # The schema constrains this, but the schema is enforced by the
            # provider and this is the boundary where that stops being our
            # guarantee. Unknown aspects are dropped rather than raised: one
            # bad entry should not discard a good analysis of the rest.
            if name not in ASPECTS or name in seen:
                continue
            try:
                score = int(raw.get("score", 0))
            except (TypeError, ValueError):
                continue
            if score not in (-1, 0, 1):
                continue
            seen.add(name)
            quote = str(raw.get("quote", "")).strip() or None
            aspects.append(AspectScore(aspect=name, score=score, quote=quote))

        try:
            sentiment = Sentiment(str(result.get("sentiment", "")))
        except ValueError as exc:
            raise errors.ModelResponseInvalidError("unknown sentiment value") from exc

        needs_attention = bool(result.get("needs_attention", False))
        return ReviewInsight(
            sentiment=sentiment,
            aspects=tuple(aspects),
            summary=str(result.get("summary", "")).strip(),
            needs_attention=needs_attention,
            attention_reason=(
                str(result.get("attention_reason", "")).strip() if needs_attention else None
            ),
        )


def tally_delta(insight: ReviewInsight) -> dict[str, Any]:
    """The per-property aggregate contribution of one insight.

    Returned as a delta rather than applied, so the caller can add it inside
    the same transaction that stores the insight. An aggregate that advanced
    for an insight that rolled back is a number nobody can reproduce.
    """
    tallies: dict[str, dict[str, int]] = {}
    for aspect in insight.aspects:
        if aspect.score == 0:
            continue
        bucket = "positive" if aspect.score > 0 else "negative"
        tallies.setdefault(aspect.aspect, {})[bucket] = 1
    return {
        "sentiment": insight.sentiment.value,
        "aspects": tallies,
    }


# ══════════════════════════════════════════════════════════════════════════
# Image tagging
# ══════════════════════════════════════════════════════════════════════════


@dataclass(slots=True)
class TagImage:
    """Describe one property photograph.

    ``known_amenities`` is the real catalogue, passed in by the caller. It does
    two things: it is given to the model so the labels come back in the
    platform's vocabulary, and it is used afterwards to discard anything that
    did not. A model that invents `"infinity_pool"` when the catalogue says
    `"pool"` produces a tag that can never match a search filter, and a tag
    that matches nothing is worse than no tag — it looks like the feature works.
    """

    model: LanguageModel

    async def execute(
        self,
        *,
        image_bytes: bytes,
        media_type: str,
        known_amenities: frozenset[str],
    ) -> ImageAnnotation:
        if not self.model.available:
            raise errors.ModelUnavailableError

        result = await self.model.describe_image(
            system=prompts.IMAGE_SYSTEM,
            user=f"AMENITY CODES: {sorted(known_amenities)}",
            image_bytes=image_bytes,
            media_type=media_type,
            schema=prompts.IMAGE_SCHEMA,
            tool_name="describe_image",
        )
        return self._parse(result, known_amenities=known_amenities)

    @staticmethod
    def _parse(result: dict[str, Any], *, known_amenities: frozenset[str]) -> ImageAnnotation:
        tags: list[ImageTag] = []
        suggested: set[str] = set()

        for raw in result.get("tags", []):
            if not isinstance(raw, dict):
                continue
            label = str(raw.get("label", "")).strip().lower()[:40]
            if not label:
                continue
            try:
                kind = TagKind(str(raw.get("kind", "descriptive")))
                confidence = float(raw.get("confidence", 0))
            except (TypeError, ValueError):
                continue
            confidence = max(0.0, min(1.0, confidence))
            tags.append(ImageTag(label=label, kind=kind, confidence=confidence))

            # Only a confident tag, and only one the catalogue knows about,
            # becomes a suggestion a host is asked to confirm.
            if (
                kind is TagKind.AMENITY
                and confidence >= AMENITY_CONFIDENCE_FLOOR
                and label in known_amenities
            ):
                suggested.add(label)

        alt_text = str(result.get("alt_text", "")).strip()
        if not alt_text:
            # Alt text is the accessibility deliverable and the one field with
            # no acceptable default. An empty alt attribute on a content image
            # is worse than a mediocre description.
            raise errors.ModelResponseInvalidError("no alt text returned")

        flagged = bool(result.get("flagged", False))
        return ImageAnnotation(
            tags=tuple(tags),
            alt_text=alt_text[:250],
            suggested_amenities=frozenset(suggested),
            flagged=flagged,
            flag_reason=(str(result.get("flag_reason", "")).strip() if flagged else None),
        )


def annotation_to_row(annotation: ImageAnnotation) -> dict[str, Any]:
    return {
        "alt_text": annotation.alt_text,
        "tags": [
            {"label": t.label, "kind": t.kind.value, "confidence": round(t.confidence, 3)}
            for t in annotation.tags
        ],
        "suggested_amenities": sorted(annotation.suggested_amenities),
        "flagged": annotation.flagged,
        "flag_reason": annotation.flag_reason,
    }


def insight_to_row(insight: ReviewInsight, *, review_id: uuid.UUID) -> dict[str, Any]:
    return {
        "review_id": review_id,
        "sentiment": insight.sentiment.value,
        "summary": insight.summary,
        "aspects": [
            {"aspect": a.aspect, "score": a.score, "quote": a.quote} for a in insight.aspects
        ],
        "positive_aspects": list(insight.positives),
        "negative_aspects": list(insight.negatives),
        "needs_attention": insight.needs_attention,
        "attention_reason": insight.attention_reason,
    }
