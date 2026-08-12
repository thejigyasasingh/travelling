"""The review transaction scope.

Holds the booking service and the property rating writer alongside the review
repository, all on **one session** — so a review, the aggregate it moves and the
property rating it publishes commit together or not at all. A rating that
advanced for a review that rolled back is a number nobody can reproduce.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.outbox import persist_events
from app.modules.booking.public import build_booking_payment_service
from app.modules.property.public import build_rating_writer
from app.modules.review.infrastructure.repositories import SqlReviewRepository


class ReviewUow:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reviews = SqlReviewRepository(session)
        # Both through their modules' published contracts — this module names
        # no other module's internals.
        self.bookings = build_booking_payment_service(session)
        self.ratings = build_rating_writer(session)

    async def flush(self) -> None:
        await self.reviews.flush()
        await persist_events(self.session, self.reviews.pending_events())

    async def commit(self) -> None:
        await self.flush()
        await self.session.commit()

    def pending_events(self) -> list[Any]:
        return self.reviews.pending_events()
