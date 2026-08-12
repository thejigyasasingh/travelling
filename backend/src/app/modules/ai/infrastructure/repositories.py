"""Persistence for generated data.

Every write here is an upsert keyed on the natural key — review id, image id,
request hash — because every one of them is driven either by an at-least-once
event or by a cache miss that two requests can hit simultaneously. There is no
insert-if-not-exists anywhere in this file; that pattern loses the race it is
written to win.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)

#: Insight upsert. The `WHERE` on the update is the idempotency: a redelivery
#: carrying the same hash changes nothing and, because `xmax` stays 0, does not
#: even dirty the page.
_UPSERT_INSIGHT = text("""
INSERT INTO review_insights
    (id, review_id, property_id, sentiment, summary, aspects,
     positive_aspects, negative_aspects, needs_attention, attention_reason,
     model, content_hash, created_at, updated_at)
VALUES
    (gen_random_uuid(), :review_id, :property_id, :sentiment, :summary,
     CAST(:aspects AS jsonb), :positive, :negative, :needs_attention,
     :attention_reason, :model, :content_hash, now(), now())
ON CONFLICT ON CONSTRAINT uq_review_insights_review DO UPDATE
   SET sentiment        = EXCLUDED.sentiment,
       summary          = EXCLUDED.summary,
       aspects          = EXCLUDED.aspects,
       positive_aspects = EXCLUDED.positive_aspects,
       negative_aspects = EXCLUDED.negative_aspects,
       needs_attention  = EXCLUDED.needs_attention,
       attention_reason = EXCLUDED.attention_reason,
       model            = EXCLUDED.model,
       content_hash     = EXCLUDED.content_hash,
       updated_at       = now(),
       -- An edited review is a new thing to look at. Clearing this puts it
       -- back in the support queue rather than leaving it dismissed on the
       -- strength of what it used to say.
       acknowledged_at  = NULL
 WHERE review_insights.content_hash <> EXCLUDED.content_hash
RETURNING (xmax = 0) AS inserted
""")

#: Recomputed rather than incremented. Unlike the rating aggregate — which is a
#: running sum over a table that only grows — sentiment counts have to survive
#: re-analysis of an existing row, and an increment cannot tell a new insight
#: from a changed one. A property's insights are bounded by its review count,
#: so the recompute is cheap and always correct.
_REBUILD_SENTIMENT = text("""
INSERT INTO property_sentiment
    (property_id, analysed_count, positive_count, mixed_count, negative_count,
     aspect_tallies, created_at, updated_at)
SELECT :property_id,
       count(*),
       count(*) FILTER (WHERE sentiment = 'positive'),
       count(*) FILTER (WHERE sentiment = 'mixed'),
       count(*) FILTER (WHERE sentiment = 'negative'),
       COALESCE((
           SELECT jsonb_object_agg(aspect, counts)
             FROM (
                 SELECT a.aspect,
                        jsonb_build_object(
                            'positive', count(*) FILTER (WHERE a.score > 0),
                            'negative', count(*) FILTER (WHERE a.score < 0)
                        ) AS counts
                   FROM review_insights ri2
                   CROSS JOIN LATERAL jsonb_to_recordset(ri2.aspects)
                        AS a(aspect text, score int)
                  WHERE ri2.property_id = :property_id
                  GROUP BY a.aspect
             ) per_aspect
       ), '{}'::jsonb),
       now(), now()
  FROM review_insights ri
 WHERE ri.property_id = :property_id
ON CONFLICT (property_id) DO UPDATE
   SET analysed_count = EXCLUDED.analysed_count,
       positive_count = EXCLUDED.positive_count,
       mixed_count    = EXCLUDED.mixed_count,
       negative_count = EXCLUDED.negative_count,
       aspect_tallies = EXCLUDED.aspect_tallies,
       updated_at     = now()
""")

_UPSERT_ANNOTATION = text("""
INSERT INTO image_annotations
    (id, image_id, property_id, alt_text, tags, suggested_amenities,
     flagged, flag_reason, model, content_hash, created_at, updated_at)
VALUES
    (gen_random_uuid(), :image_id, :property_id, :alt_text, CAST(:tags AS jsonb),
     :suggested, :flagged, :flag_reason, :model, :content_hash, now(), now())
ON CONFLICT ON CONSTRAINT uq_image_annotations_image DO UPDATE
   SET alt_text            = EXCLUDED.alt_text,
       tags                = EXCLUDED.tags,
       suggested_amenities = EXCLUDED.suggested_amenities,
       flagged             = EXCLUDED.flagged,
       flag_reason         = EXCLUDED.flag_reason,
       model               = EXCLUDED.model,
       content_hash        = EXCLUDED.content_hash,
       updated_at          = now(),
       reviewed_at         = NULL
 WHERE image_annotations.content_hash <> EXCLUDED.content_hash
""")

_UPSERT_ITINERARY = text("""
INSERT INTO generated_itineraries
    (id, request_hash, city, days, summary, plan, referenced_property_ids,
     low_confidence, model, hit_count, expires_at, created_at, updated_at)
VALUES
    (gen_random_uuid(), :hash, :city, :days, :summary, CAST(:plan AS jsonb),
     CAST(:refs AS uuid[]), :low_confidence, :model, 0, :expires_at, now(), now())
ON CONFLICT ON CONSTRAINT uq_generated_itineraries_hash DO UPDATE
   SET plan       = EXCLUDED.plan,
       summary    = EXCLUDED.summary,
       expires_at = EXCLUDED.expires_at,
       updated_at = now()
""")


class AIRepository:
    """Everything the AI module stores. One class because none of it is an
    aggregate — there is no invariant here that spans two rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── review insights ───────────────────────────────────────────────────

    async def save_insight(
        self,
        *,
        review_id: uuid.UUID,
        property_id: uuid.UUID,
        row: dict[str, Any],
        model: str,
        content_hash: str,
    ) -> bool:
        """Returns whether anything changed.

        False means a redelivery of an unchanged review, and the caller skips
        the aggregate rebuild — the counts cannot have moved.
        """
        from app.modules.ai.application.prompts import dumps

        result = (
            await self._session.execute(
                _UPSERT_INSIGHT,
                {
                    "review_id": review_id,
                    "property_id": property_id,
                    "sentiment": row["sentiment"],
                    "summary": row["summary"],
                    "aspects": dumps(row["aspects"]),
                    "positive": row["positive_aspects"],
                    "negative": row["negative_aspects"],
                    "needs_attention": row["needs_attention"],
                    "attention_reason": row["attention_reason"],
                    "model": model,
                    "content_hash": content_hash,
                },
            )
        ).first()
        return result is not None

    async def rebuild_sentiment(self, property_id: uuid.UUID) -> None:
        await self._session.execute(_REBUILD_SENTIMENT, {"property_id": property_id})

    async def sentiment_for(self, property_id: uuid.UUID) -> dict[str, Any] | None:
        row = (
            await self._session.execute(
                text("""
                SELECT analysed_count, positive_count, mixed_count,
                       negative_count, aspect_tallies
                  FROM property_sentiment WHERE property_id = :pid
                """),
                {"pid": property_id},
            )
        ).first()
        if row is None or row[0] == 0:
            return None
        return {
            "analysed_count": row[0],
            "positive_count": row[1],
            "mixed_count": row[2],
            "negative_count": row[3],
            "aspects": row[4] or {},
        }

    async def insights_for(
        self, property_id: uuid.UUID, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                text("""
                SELECT ri.review_id, ri.sentiment, ri.summary, ri.aspects
                  FROM review_insights ri
                  JOIN reviews r ON r.id = ri.review_id
                 -- A removed review's analysis must not outlive it on the page.
                 WHERE ri.property_id = :pid AND r.moderation <> 'removed'
                 ORDER BY ri.created_at DESC
                 LIMIT :limit
                """),
                {"pid": property_id, "limit": limit},
            )
        ).all()
        return [
            {
                "review_id": str(r[0]),
                "sentiment": r[1],
                "summary": r[2],
                "aspects": r[3] or [],
            }
            for r in rows
        ]

    async def attention_queue(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                text("""
                SELECT ri.id, ri.review_id, ri.property_id, p.name,
                       ri.attention_reason, ri.summary, ri.created_at
                  FROM review_insights ri
                  JOIN properties p ON p.id = ri.property_id
                 WHERE ri.needs_attention AND ri.acknowledged_at IS NULL
                 ORDER BY ri.created_at
                 LIMIT :limit
                """),
                {"limit": limit},
            )
        ).all()
        return [
            {
                "id": str(r[0]),
                "review_id": str(r[1]),
                "property_id": str(r[2]),
                "property_name": r[3],
                "reason": r[4],
                "summary": r[5],
                "created_at": r[6],
            }
            for r in rows
        ]

    async def acknowledge(self, insight_id: uuid.UUID) -> bool:
        result = cast(
            "CursorResult[Any]",
            await self._session.execute(
                text(
                    "UPDATE review_insights SET acknowledged_at = now(), updated_at = now() "
                    " WHERE id = :id AND acknowledged_at IS NULL"
                ),
                {"id": insight_id},
            ),
        )
        return bool(result.rowcount)

    # ── image annotations ─────────────────────────────────────────────────

    async def save_annotation(
        self,
        *,
        image_id: uuid.UUID,
        property_id: uuid.UUID,
        row: dict[str, Any],
        model: str,
        content_hash: str,
    ) -> None:
        from app.modules.ai.application.prompts import dumps

        await self._session.execute(
            _UPSERT_ANNOTATION,
            {
                "image_id": image_id,
                "property_id": property_id,
                "alt_text": row["alt_text"],
                "tags": dumps(row["tags"]),
                "suggested": row["suggested_amenities"],
                "flagged": row["flagged"],
                "flag_reason": row["flag_reason"],
                "model": model,
                "content_hash": content_hash,
            },
        )

    async def annotations_for(self, property_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                text("""
                SELECT image_id, alt_text, tags, suggested_amenities,
                       flagged, flag_reason, reviewed_at
                  FROM image_annotations
                 WHERE property_id = :pid
                 ORDER BY created_at
                """),
                {"pid": property_id},
            )
        ).all()
        return [
            {
                "image_id": str(r[0]),
                "alt_text": r[1],
                "tags": r[2] or [],
                "suggested_amenities": list(r[3] or []),
                "flagged": r[4],
                "flag_reason": r[5],
                "reviewed": r[6] is not None,
            }
            for r in rows
        ]

    # ── itineraries ───────────────────────────────────────────────────────

    async def cached_itinerary(self, request_hash: str) -> dict[str, Any] | None:
        """Read and count the hit in one statement.

        The count is what tells you whether the cache is earning its keep. Done
        as an UPDATE … RETURNING rather than a read followed by a write so a
        popular itinerary does not serialise every reader behind a counter.
        """
        row = (
            await self._session.execute(
                text("""
                UPDATE generated_itineraries
                   SET hit_count = hit_count + 1
                 WHERE request_hash = :hash AND expires_at > now()
             RETURNING plan, summary, low_confidence, city
                """),
                {"hash": request_hash},
            )
        ).first()
        if row is None:
            return None
        return {
            **(row[0] or {}),
            "summary": row[1],
            "low_confidence": row[2],
            "city": row[3],
        }

    async def save_itinerary(
        self,
        *,
        request_hash: str,
        city: str,
        days: int,
        summary: str,
        plan: dict[str, Any],
        referenced: list[uuid.UUID],
        low_confidence: bool,
        model: str,
        expires_at: datetime,
    ) -> None:
        from app.modules.ai.application.prompts import dumps

        await self._session.execute(
            _UPSERT_ITINERARY,
            {
                "hash": request_hash,
                "city": city,
                "days": days,
                "summary": summary,
                "plan": dumps(plan),
                "refs": [str(pid) for pid in referenced],
                "low_confidence": low_confidence,
                "model": model,
                "expires_at": expires_at,
            },
        )

    async def invalidate_itineraries_referencing(self, property_id: uuid.UUID) -> int:
        """Expire every cached plan that points at this property.

        Called when a listing is unpublished or deleted. Expiring rather than
        deleting keeps the row for the hit-count history, and costs one
        comparison on read.
        """
        result = cast(
            "CursorResult[Any]",
            await self._session.execute(
                text(
                    "UPDATE generated_itineraries SET expires_at = now(), updated_at = now() "
                    " WHERE :pid = ANY(referenced_property_ids) AND expires_at > now()"
                ),
                {"pid": property_id},
            ),
        )
        return int(result.rowcount or 0)

    # ── conversations ─────────────────────────────────────────────────────

    async def append_message(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID | None,
        role: str,
        content: str,
        suggested: list[uuid.UUID] | None = None,
        needs_human: bool = False,
    ) -> None:
        await self._session.execute(
            text("""
            INSERT INTO assistant_messages
                (id, conversation_id, user_id, role, content,
                 suggested_property_ids, needs_human, created_at)
            VALUES (gen_random_uuid(), :cid, :uid, :role, :content,
                    CAST(:suggested AS uuid[]), :needs_human, now())
            """),
            {
                "cid": conversation_id,
                "uid": user_id,
                "role": role,
                "content": content,
                "suggested": [str(pid) for pid in (suggested or [])],
                "needs_human": needs_human,
            },
        )

    async def conversation(
        self, conversation_id: uuid.UUID, *, user_id: uuid.UUID | None, limit: int = 12
    ) -> list[dict[str, Any]]:
        """Load a thread, scoped to its owner.

        The `user_id` predicate is the authorisation, and it is written as part
        of the query rather than checked afterwards. A conversation id is a
        UUIDv7 and therefore guessable-adjacent; without this, knowing one
        would be enough to read someone else's chat.
        """
        rows = (
            await self._session.execute(
                text("""
                SELECT role, content
                  FROM assistant_messages
                 WHERE conversation_id = :cid
                   AND user_id IS NOT DISTINCT FROM :uid
                 ORDER BY created_at DESC
                 LIMIT :limit
                """),
                {"cid": conversation_id, "uid": user_id, "limit": limit},
            )
        ).all()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    async def purge_messages_older_than(self, days: int) -> int:
        result = cast(
            "CursorResult[Any]",
            await self._session.execute(
                text(
                    "DELETE FROM assistant_messages "
                    " WHERE created_at < now() - make_interval(days => :days)"
                ),
                {"days": days},
            ),
        )
        return int(result.rowcount or 0)

    # ── usage ─────────────────────────────────────────────────────────────

    async def record_usage(
        self,
        *,
        user_id: uuid.UUID | None,
        feature: str,
        model: str,
        latency_ms: int,
        succeeded: bool,
    ) -> None:
        await self._session.execute(
            text("""
            INSERT INTO ai_usage
                (id, user_id, feature, model, latency_ms, succeeded, created_at)
            VALUES (gen_random_uuid(), :uid, :feature, :model, :latency, :ok, now())
            """),
            {
                "uid": user_id,
                "feature": feature,
                "model": model,
                "latency": latency_ms,
                "ok": succeeded,
            },
        )

    async def flush(self) -> None:
        await self._session.flush()
