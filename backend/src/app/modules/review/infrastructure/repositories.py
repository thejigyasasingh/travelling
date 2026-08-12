"""Review persistence, and the rating aggregate it maintains."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import UnaryExpression

from app.modules.review.domain import errors
from app.modules.review.domain.entities import Review
from app.modules.review.domain.value_objects import ModerationState, Rating
from app.modules.review.infrastructure.models import ReviewModel, ReviewRatingSummary


def _to_domain(row: ReviewModel) -> Review:
    return Review(
        entity_id=row.id,
        booking_id=row.booking_id,
        property_id=row.property_id,
        vendor_id=row.vendor_id,
        author_id=row.author_id,
        author_name=row.author_name,
        rating=Rating(row.rating),
        title=row.title,
        body=row.body,
        categories=dict(row.categories or {}),
        created_at=row.published_at,
        stayed_on=row.stayed_on,
        moderation=ModerationState(row.moderation),
        moderation_note=row.moderation_note,
        host_reply=row.host_reply,
        host_replied_at=row.host_replied_at,
        edited_at=row.edited_at,
        version=row.version,
    )


#: Apply one review to a property's rating aggregate.
#:
#: `delta` is +1 when a review lands and -1 when one is removed, so the same
#: statement serves both. The upsert is what makes it safe under concurrency:
#: two reviews landing on the same property in the same instant both add, and
#: neither reads a total the other is about to change.
#:
#: **The GREATEST in the VALUES clause is not redundant.** Postgres evaluates
#: CHECK constraints against the row *proposed* for insertion, before it
#: arbitrates the conflict — so on a property that already has a summary row, a
#: negative delta raises `ck_rating_summaries_count_non_negative` from a branch
#: that is never taken. Every rating decrease and every removal 409s. Clamping
#: here is also the right semantic for the branch that *is* taken on a genuine
#: first insert: there is no prior review to subtract, so the row starts at
#: zero.
_APPLY_RATING_SQL = """
INSERT INTO review_rating_summaries AS s
       (property_id, review_count, rating_total,
        count_1, count_2, count_3, count_4, count_5, updated_at)
VALUES (:property_id, GREATEST(:delta, 0), GREATEST(:rating_delta, 0),
        GREATEST(:c1, 0), GREATEST(:c2, 0), GREATEST(:c3, 0),
        GREATEST(:c4, 0), GREATEST(:c5, 0), now())
ON CONFLICT (property_id) DO UPDATE
   SET review_count = GREATEST(s.review_count + :delta, 0),
       rating_total = GREATEST(s.rating_total + :rating_delta, 0),
       count_1      = GREATEST(s.count_1 + :c1, 0),
       count_2      = GREATEST(s.count_2 + :c2, 0),
       count_3      = GREATEST(s.count_3 + :c3, 0),
       count_4      = GREATEST(s.count_4 + :c4, 0),
       count_5      = GREATEST(s.count_5 + :c5, 0),
       updated_at   = now()
RETURNING review_count, rating_total
"""


class SqlReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._identity: dict[uuid.UUID, tuple[Review, ReviewModel]] = {}

    async def get(self, review_id: uuid.UUID) -> Review | None:
        if review_id in self._identity:
            return self._identity[review_id][0]
        return self._track(await self._session.get(ReviewModel, review_id))

    async def get_for_booking(self, booking_id: uuid.UUID) -> Review | None:
        row = (
            await self._session.execute(
                select(ReviewModel).where(ReviewModel.booking_id == booking_id)
            )
        ).scalar_one_or_none()
        return self._track(row)

    async def add(self, review: Review) -> None:
        row = ReviewModel(
            id=review.id,
            booking_id=review.booking_id,
            property_id=review.property_id,
            vendor_id=review.vendor_id,
            author_id=review.author_id,
            author_name=review.author_name,
            rating=int(review.rating),
            title=review.title,
            body=review.body,
            categories=review.categories,
            stayed_on=review.stayed_on,
            moderation=review.moderation.value,
            published_at=review.created_at,
        )
        self._session.add(row)
        self._identity[review.id] = (review, row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # The unique index, not a prior SELECT: two submissions of the same
            # form both pass a check-then-act.
            raise errors.AlreadyReviewedError from exc

    async def apply_to_rating(
        self, *, property_id: uuid.UUID, rating: int, delta: int
    ) -> tuple[int, float]:
        """Fold one review into the property's aggregate.

        Returns the new count and average, which the caller writes back to the
        `properties` row through that module's published contract — this module
        does not touch another module's table.
        """
        buckets = {f"c{n}": (delta if n == rating else 0) for n in range(1, 6)}
        row = (
            await self._session.execute(
                text(_APPLY_RATING_SQL),
                {
                    "property_id": property_id,
                    "delta": delta,
                    "rating_delta": rating * delta,
                    **buckets,
                },
            )
        ).one()
        count, total = int(row[0]), int(row[1])
        return count, (round(total / count, 2) if count else 0.0)

    async def summary(self, property_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self._session.get(ReviewRatingSummary, property_id)
        if row is None or row.review_count == 0:
            return None
        return {
            "count": row.review_count,
            "average": round(row.rating_total / row.review_count, 2),
            "distribution": {
                1: row.count_1,
                2: row.count_2,
                3: row.count_3,
                4: row.count_4,
                5: row.count_5,
            },
        }

    async def list_for_property(
        self,
        property_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
        sort: str = "recent",
    ) -> tuple[list[Review], int]:
        stmt = select(ReviewModel).where(
            ReviewModel.property_id == property_id,
            # Flagged reviews stay visible; only removed ones disappear.
            ReviewModel.moderation != ModerationState.REMOVED.value,
        )
        # A dict literal of ORDER BY clauses infers as `object`; the mapping is
        # declared so an unknown sort falls back rather than reaching SQLAlchemy.
        orders: dict[str, UnaryExpression[Any]] = {
            "recent": ReviewModel.published_at.desc(),
            "rating_desc": ReviewModel.rating.desc(),
            "rating_asc": ReviewModel.rating.asc(),
        }
        order = orders.get(sort, orders["recent"])

        rows = (
            (await self._session.execute(stmt.order_by(order).limit(limit).offset(offset)))
            .scalars()
            .all()
        )
        total = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(ReviewModel)
                    .where(
                        ReviewModel.property_id == property_id,
                        ReviewModel.moderation != ModerationState.REMOVED.value,
                    )
                )
            ).scalar()
            or 0
        )
        return [r for r in (self._track(row) for row in rows) if r is not None], total

    async def list_for_author(self, author_id: uuid.UUID, *, limit: int = 50) -> list[Review]:
        """A guest's own reviews.

        Includes removed ones, unlike every other read. The author is the one
        person entitled to know their review was taken down — discovering it
        only by its absence from a property page is how a moderation decision
        becomes a support ticket.

        Unpaginated and capped: a guest has as many reviews as they have stays,
        and paging a list that is almost always under ten is machinery nobody
        needs.
        """
        rows = (
            (
                await self._session.execute(
                    select(ReviewModel)
                    .where(ReviewModel.author_id == author_id)
                    .order_by(ReviewModel.published_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [r for r in (self._track(row) for row in rows) if r is not None]

    async def list_for_vendor(
        self,
        vendor_id: uuid.UUID,
        *,
        awaiting_reply: bool = False,
        property_id: uuid.UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Review], int]:
        """The vendor's queue.

        Unanswered first when asked for, because replying is the only action a
        vendor can take here and a list sorted purely by date buries it.
        """
        conditions = [ReviewModel.vendor_id == vendor_id]
        if awaiting_reply:
            conditions += [
                ReviewModel.host_reply.is_(None),
                ReviewModel.moderation != ModerationState.REMOVED.value,
            ]
        if property_id is not None:
            conditions.append(ReviewModel.property_id == property_id)

        rows = (
            (
                await self._session.execute(
                    select(ReviewModel)
                    .where(*conditions)
                    .order_by(ReviewModel.published_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(ReviewModel).where(*conditions)
                )
            ).scalar()
            or 0
        )
        return [r for r in (self._track(row) for row in rows) if r is not None], total

    async def vendor_summary(self, vendor_id: uuid.UUID) -> dict[str, Any]:
        """What the portal's reviews tile shows."""
        row = (
            await self._session.execute(
                text(
                    "SELECT count(*)                                             AS total, "
                    "       COALESCE(avg(rating), 0)                             AS average, "
                    "       count(*) FILTER (WHERE host_reply IS NULL "
                    "                          AND moderation <> 'removed')      AS awaiting, "
                    "       count(*) FILTER (WHERE rating <= 2 "
                    "                          AND moderation <> 'removed')      AS critical "
                    "  FROM reviews WHERE vendor_id = :vendor_id "
                    "   AND moderation <> 'removed'"
                ),
                {"vendor_id": vendor_id},
            )
        ).one()
        return {
            "total": int(row[0]),
            "average": round(float(row[1]), 2),
            "awaiting_reply": int(row[2]),
            "critical": int(row[3]),
        }

    async def flush(self) -> None:
        for review, row in self._identity.values():
            row.rating = int(review.rating)
            row.title = review.title
            row.body = review.body
            row.categories = review.categories
            row.moderation = review.moderation.value
            row.moderation_note = review.moderation_note
            row.host_reply = review.host_reply
            row.host_replied_at = review.host_replied_at
            row.edited_at = review.edited_at
        await self._session.flush()

    def pending_events(self) -> list[Any]:
        events: list[Any] = []
        for review, _ in self._identity.values():
            events.extend(review.pull_events())
        return events

    def _track(self, row: ReviewModel | None) -> Review | None:
        if row is None:
            return None
        if row.id in self._identity:
            return self._identity[row.id][0]
        review = _to_domain(row)
        self._identity[row.id] = (review, row)
        return review


def now_utc() -> datetime:  # pragma: no cover — re-exported for tasks
    from app.core.clock import utcnow

    return utcnow()
