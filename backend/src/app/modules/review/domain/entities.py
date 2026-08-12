"""Reviews.

The rule that makes a review worth reading is that the author demonstrably
stayed there. A review platform where anyone can post is a review platform
nobody believes, and it is the single feature competitors forge at scale.

So a review is created **from a completed booking**, not from a property id:
the booking is the evidence, and one booking yields one review. Everything else
here follows from that — the editing window, the moderation states, the host's
right of reply.

Ratings are integers 1 to 5. Not decimals: a guest cannot meaningfully distinguish
3.7 from 3.8, and averaging integers is what produces the decimal on the
property page.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Final

from app.modules.review.domain import errors
from app.modules.review.domain.events import (
    HostReplied,
    ReviewEdited,
    ReviewPublished,
    ReviewRemoved,
)
from app.modules.review.domain.value_objects import (
    RATING_CATEGORIES,
    ModerationState,
    Rating,
)
from app.shared.domain.entity import AggregateRoot

#: A guest may correct a review for this long. After that it is the historical
#: record — a host who has replied should not find the review rewritten under
#: their answer.
EDIT_WINDOW: Final = timedelta(hours=48)

#: A stay must be reviewed within this window. Beyond it, memory is unreliable
#: and the review says more about the interval than the stay.
REVIEW_WINDOW_DAYS: Final = 90

MIN_BODY: Final = 40
MAX_BODY: Final = 4000


class Review(AggregateRoot):
    """One guest's account of one stay."""

    __slots__ = (
        "author_id",
        "author_name",
        "body",
        "booking_id",
        "categories",
        "created_at",
        "edited_at",
        "host_replied_at",
        "host_reply",
        "moderation",
        "moderation_note",
        "property_id",
        "rating",
        "stayed_on",
        "title",
        "vendor_id",
    )

    def __init__(
        self,
        *,
        entity_id: uuid.UUID | None = None,
        booking_id: uuid.UUID,
        property_id: uuid.UUID,
        vendor_id: uuid.UUID,
        author_id: uuid.UUID,
        author_name: str,
        rating: Rating,
        body: str,
        created_at: datetime,
        title: str | None = None,
        categories: dict[str, int] | None = None,
        stayed_on: datetime | None = None,
        moderation: ModerationState = ModerationState.PUBLISHED,
        moderation_note: str | None = None,
        host_reply: str | None = None,
        host_replied_at: datetime | None = None,
        edited_at: datetime | None = None,
        version: int = 1,
    ) -> None:
        super().__init__(entity_id, version)
        self.booking_id = booking_id
        self.property_id = property_id
        self.vendor_id = vendor_id
        self.author_id = author_id
        self.author_name = author_name
        self.rating = rating
        self.title = title
        self.body = body
        self.categories = categories or {}
        self.created_at = created_at
        self.stayed_on = stayed_on
        self.moderation = moderation
        self.moderation_note = moderation_note
        self.host_reply = host_reply
        self.host_replied_at = host_replied_at
        self.edited_at = edited_at

    @classmethod
    def write(
        cls,
        *,
        booking_id: uuid.UUID,
        property_id: uuid.UUID,
        vendor_id: uuid.UUID,
        author_id: uuid.UUID,
        author_name: str,
        rating: int,
        body: str,
        now: datetime,
        checked_out_at: datetime,
        title: str | None = None,
        categories: dict[str, int] | None = None,
    ) -> Review:
        """Write a review of a completed stay.

        The caller has already established that the booking belongs to this
        guest and is complete — that check needs the booking module and lives in
        the use case. What lives here is everything that is true of a review
        regardless of who is asking.
        """
        if now - checked_out_at > timedelta(days=REVIEW_WINDOW_DAYS):
            raise errors.ReviewWindowClosedError(REVIEW_WINDOW_DAYS)

        trimmed = body.strip()
        if len(trimmed) < MIN_BODY:
            raise errors.ReviewTooShortError(MIN_BODY)
        if len(trimmed) > MAX_BODY:
            trimmed = trimmed[:MAX_BODY]

        cleaned = _validate_categories(categories or {})

        review = cls(
            booking_id=booking_id,
            property_id=property_id,
            vendor_id=vendor_id,
            author_id=author_id,
            author_name=author_name,
            rating=Rating(rating),
            title=(title or "").strip()[:120] or None,
            body=trimmed,
            categories=cleaned,
            created_at=now,
            stayed_on=checked_out_at,
        )
        review.record(
            ReviewPublished(
                aggregate_id=review.id,
                property_id=property_id,
                vendor_id=vendor_id,
                booking_id=booking_id,
                rating=int(review.rating),
                author_name=author_name,
            )
        )
        return review

    # ── the guest's rights ────────────────────────────────────────────────

    def edit(
        self,
        *,
        rating: int | None,
        title: str | None,
        body: str | None,
        categories: dict[str, int] | None,
        now: datetime,
    ) -> None:
        """Correct a review, within the window.

        Closed once the host has replied, whatever the clock says: rewriting a
        review under an answer that addressed the original is a way to make a
        host look evasive.
        """
        if self.host_reply is not None:
            raise errors.ReviewLockedError("the host has already replied")
        if now - self.created_at > EDIT_WINDOW:
            raise errors.ReviewLockedError("the editing window has closed")

        if rating is not None:
            self.rating = Rating(rating)
        if title is not None:
            self.title = title.strip()[:120] or None
        if body is not None:
            trimmed = body.strip()
            if len(trimmed) < MIN_BODY:
                raise errors.ReviewTooShortError(MIN_BODY)
            self.body = trimmed[:MAX_BODY]
        if categories is not None:
            self.categories = _validate_categories(categories)

        self.edited_at = now
        # Anything derived from the text — the rating aggregate, the sentiment
        # analysis — is now describing words the guest has replaced.
        self.record(
            ReviewEdited(
                aggregate_id=self.id,
                property_id=self.property_id,
                rating=int(self.rating),
            )
        )

    # ── the host's right of reply ─────────────────────────────────────────

    def reply(self, *, body: str, now: datetime, vendor_id: uuid.UUID) -> None:
        """The host answers, once.

        One reply, not a thread: a review page that becomes an argument helps
        nobody reading it, and the guest's own recourse is support rather than
        a rebuttal.
        """
        if vendor_id != self.vendor_id:
            raise errors.ReviewAccessDeniedError
        if self.moderation is ModerationState.REMOVED:
            raise errors.ReviewLockedError("this review has been removed")
        if self.host_reply is not None:
            raise errors.ReviewLockedError("you have already replied")

        trimmed = body.strip()
        if len(trimmed) < 10:
            raise errors.ReviewTooShortError(10)

        self.host_reply = trimmed[:MAX_BODY]
        self.host_replied_at = now
        self.record(
            HostReplied(
                aggregate_id=self.id,
                property_id=self.property_id,
                vendor_id=self.vendor_id,
                author_id=self.author_id,
                preview=self.host_reply[:120],
            )
        )

    # ── moderation ────────────────────────────────────────────────────────

    def flag(self, *, reason: str) -> None:
        """A host disputes a review.

        Flagging does **not** hide it. A listing that could suppress criticism
        by objecting to it is a listing whose rating means nothing — so the
        review stays visible and counted while a human looks.
        """
        if self.moderation is ModerationState.REMOVED:
            return
        self.moderation = ModerationState.FLAGGED
        self.moderation_note = reason.strip()[:500]

    def remove(self, *, reason: str, now: datetime) -> None:
        """Take a review down and stop it counting.

        For the narrow cases that justify it — personal data, a threat, a
        review of the wrong property. Not for being negative.
        """
        if not reason.strip():
            raise errors.ModerationReasonRequiredError
        self.moderation = ModerationState.REMOVED
        self.moderation_note = reason.strip()[:500]
        self.record(
            ReviewRemoved(
                aggregate_id=self.id,
                property_id=self.property_id,
                rating=int(self.rating),
                reason=self.moderation_note,
                removed_at=now,
            )
        )

    def restore(self) -> None:
        self.moderation = ModerationState.PUBLISHED
        self.moderation_note = None

    # ── what other code asks ──────────────────────────────────────────────

    @property
    def is_visible(self) -> bool:
        """Flagged reviews stay visible — see `flag`."""
        return self.moderation is not ModerationState.REMOVED

    @property
    def counts_towards_rating(self) -> bool:
        return self.is_visible

    def can_edit(self, now: datetime) -> bool:
        return self.host_reply is None and now - self.created_at <= EDIT_WINDOW

    def as_audit(self) -> dict[str, Any]:
        return {
            "review_id": str(self.id),
            "property_id": str(self.property_id),
            "rating": int(self.rating),
            "moderation": self.moderation.value,
        }


def _validate_categories(categories: dict[str, int]) -> dict[str, int]:
    """Keep the known categories, drop the rest.

    Unknown keys are dropped rather than rejected: a newer client sending a
    category this version has not heard of should still produce a review, not
    an error the guest cannot act on.
    """
    cleaned: dict[str, int] = {}
    for key, value in categories.items():
        if key not in RATING_CATEGORIES:
            continue
        cleaned[key] = int(Rating(value))
    return cleaned
