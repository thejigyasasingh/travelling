"""Review use cases.

The one that matters is `WriteReview`: it is where "you must have stayed here"
is actually enforced, by asking the booking module rather than trusting the
client. Everything else is a permission check and a state change.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.clock import Clock
from app.core.logging import get_logger
from app.modules.booking.public import BookingPaymentService
from app.modules.property.public.contract import RatingWriter
from app.modules.review.application.dto import ReviewDraft
from app.modules.review.application.ports import ReviewRepository
from app.modules.review.domain import errors
from app.modules.review.domain.entities import Review
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

MODERATOR_ROLES = ("admin", "superadmin", "support")


@dataclass(slots=True)
class WriteReview:
    """Write a review of a completed stay.

    Three facts are established before the aggregate is built, and all three
    come from the booking, not from the request:

    * the booking belongs to this guest — otherwise anyone could review
      anything by guessing an id;
    * the stay is **complete** — a review written from the lobby is not a
      review of the stay;
    * which property and vendor it was for — so a guest cannot review one
      property using another's booking.
    """

    reviews: ReviewRepository
    bookings: BookingPaymentService
    ratings: RatingWriter
    clock: Clock

    async def execute(self, draft: ReviewDraft, actor: Actor) -> Review:
        booking = await self.bookings.snapshot(draft.booking_id)
        if booking is None or booking.guest_id != actor.user_id:
            # 404 rather than 403: distinguishing the two lets someone probe
            # for booking ids.
            raise errors.ReviewAccessDeniedError
        if not booking.is_reviewable:
            raise errors.StayNotCompletedError

        existing = await self.reviews.get_for_booking(draft.booking_id)
        if existing is not None:
            raise errors.AlreadyReviewedError

        now = self.clock.now()
        review = Review.write(
            booking_id=booking.id,
            property_id=booking.property_id,
            vendor_id=booking.vendor_id,
            author_id=booking.guest_id,
            author_name=booking.guest_name,
            rating=draft.rating,
            body=draft.body,
            title=draft.title,
            categories=draft.categories,
            now=now,
            # Midnight on the checkout date is close enough to measure a
            # 90-day window from, and avoids depending on a checkout *time*
            # the booking module may change.
            checked_out_at=now.replace(
                year=booking.check_out.year,
                month=booking.check_out.month,
                day=booking.check_out.day,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            ),
        )
        await self.reviews.add(review)
        await self._refresh_rating(review.property_id, int(review.rating), delta=1)

        logger.info(
            "review_published",
            review_id=str(review.id),
            property_id=str(review.property_id),
            rating=int(review.rating),
        )
        return review

    async def _refresh_rating(self, property_id: uuid.UUID, rating: int, *, delta: int) -> None:
        count, average = await self.reviews.apply_to_rating(
            property_id=property_id, rating=rating, delta=delta
        )
        # Through property's published contract — this module never writes to
        # another module's table.
        await self.ratings.set_rating(property_id, average=average, count=count)


@dataclass(slots=True)
class ReplyToReview:
    """The host's one answer."""

    reviews: ReviewRepository
    clock: Clock

    async def execute(self, review_id: uuid.UUID, body: str, actor: Actor) -> Review:
        review = await self.reviews.get(review_id)
        if review is None:
            raise errors.ReviewNotFoundError
        if actor.vendor_id is None:
            raise errors.ReviewAccessDeniedError

        review.reply(body=body, now=self.clock.now(), vendor_id=actor.vendor_id)
        logger.info("review_reply_published", review_id=str(review.id))
        return review


@dataclass(slots=True)
class FlagReview:
    """A host disputes a review.

    Deliberately does not hide it. A listing that could suppress criticism by
    objecting to it is a listing whose rating means nothing.
    """

    reviews: ReviewRepository
    clock: Clock

    async def execute(self, review_id: uuid.UUID, reason: str, actor: Actor) -> Review:
        review = await self.reviews.get(review_id)
        if review is None:
            raise errors.ReviewNotFoundError
        if actor.vendor_id is None or review.vendor_id != actor.vendor_id:
            raise errors.ReviewAccessDeniedError

        review.flag(reason=reason)
        logger.info(
            "review_flagged",
            review_id=str(review.id),
            vendor_id=str(actor.vendor_id),
        )
        return review


@dataclass(slots=True)
class ModerateReview:
    """Remove or restore. Staff only."""

    reviews: ReviewRepository
    ratings: RatingWriter
    clock: Clock

    async def execute(
        self, review_id: uuid.UUID, *, remove: bool, reason: str, actor: Actor
    ) -> Review:
        if not actor.has_role(*MODERATOR_ROLES):
            raise errors.ReviewAccessDeniedError

        review = await self.reviews.get(review_id)
        if review is None:
            raise errors.ReviewNotFoundError

        was_counted = review.counts_towards_rating
        if remove:
            review.remove(reason=reason, now=self.clock.now())
        else:
            review.restore()

        # The aggregate only moves when visibility actually changed — removing
        # an already-removed review must not subtract twice.
        if was_counted != review.counts_towards_rating:
            delta = 1 if review.counts_towards_rating else -1
            count, average = await self.reviews.apply_to_rating(
                property_id=review.property_id, rating=int(review.rating), delta=delta
            )
            await self.ratings.set_rating(review.property_id, average=average, count=count)

        logger.warning(
            "review_moderated",
            review_id=str(review.id),
            removed=remove,
            by=str(actor.user_id),
        )
        return review


@dataclass(slots=True)
class EditReview:
    reviews: ReviewRepository
    ratings: RatingWriter
    clock: Clock

    async def execute(self, review_id: uuid.UUID, draft: ReviewDraft, actor: Actor) -> Review:
        review = await self.reviews.get(review_id)
        if review is None or review.author_id != actor.user_id:
            raise errors.ReviewAccessDeniedError

        previous = int(review.rating)
        review.edit(
            rating=draft.rating,
            title=draft.title,
            body=draft.body,
            categories=draft.categories,
            now=self.clock.now(),
        )

        if previous != int(review.rating):
            # Retract the old score and apply the new one, rather than trying to
            # nudge an average — the distribution has to move too.
            await self.reviews.apply_to_rating(
                property_id=review.property_id, rating=previous, delta=-1
            )
            count, average = await self.reviews.apply_to_rating(
                property_id=review.property_id, rating=int(review.rating), delta=1
            )
            await self.ratings.set_rating(review.property_id, average=average, count=count)

        return review
