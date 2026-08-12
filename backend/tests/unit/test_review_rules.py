"""Review rules.

A review is the one thing on this platform written by someone with nothing to
gain and read by everyone deciding whether to spend money. Two failure modes
matter, and they pull in opposite directions:

* a review that should not exist — invented stays, one guest posting ten times,
  a competitor's review of a property they never visited;
* a review that quietly stops existing — a host who dislikes it flags it away,
  or an edit rewrites history under a reply that was answering something else.

The rules below are the ones that hold those two apart. Each test names the
thing that goes wrong when it stops holding.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.review.domain import errors
from app.modules.review.domain.entities import EDIT_WINDOW, REVIEW_WINDOW_DAYS, Review
from app.modules.review.domain.value_objects import ModerationState, Rating

pytestmark = pytest.mark.unit

NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
CHECKED_OUT = NOW - timedelta(days=3)

GUEST = uuid.uuid4()
PROPERTY = uuid.uuid4()
VENDOR = uuid.uuid4()
BOOKING = uuid.uuid4()

LONG_ENOUGH = (
    "The room was clean and the host answered every message within minutes. "
    "The lane outside is noisier than the photographs suggest."
)


def write(
    *,
    rating: int = 5,
    body: str = LONG_ENOUGH,
    checked_out: datetime = CHECKED_OUT,
    now: datetime = NOW,
) -> Review:
    return Review.write(
        booking_id=BOOKING,
        property_id=PROPERTY,
        vendor_id=VENDOR,
        author_id=GUEST,
        author_name="Rhea M.",
        rating=rating,
        title="A quiet week",
        body=body,
        categories={"cleanliness": 5, "location": 3},
        checked_out_at=checked_out,
        now=now,
    )


# ══════════════════════════════════════════════════════════════════════════
# Who may write one
# ══════════════════════════════════════════════════════════════════════════


def test_a_completed_stay_can_be_reviewed() -> None:
    review = write()
    assert review.moderation is ModerationState.PUBLISHED
    assert int(review.rating) == 5


def test_a_future_checkout_is_inside_the_window_not_outside_it() -> None:
    """The entity polices the *far* edge, not the near one.

    Whether the stay has finished at all is the use case's question — it needs
    the booking module to answer it, and this entity deliberately cannot reach
    that far. Pinning the behaviour here so nobody later reads the absence of a
    check as the absence of a rule: :class:`StayNotCompletedError` is raised
    one layer up.
    """
    review = write(checked_out=NOW + timedelta(days=2))
    assert review.moderation is ModerationState.PUBLISHED


def test_the_review_window_closes() -> None:
    """Memory of a stay is not indefinite, and neither is the property.

    A review written two years later describes a building under different
    management, and the guest cannot be asked about it.
    """
    with pytest.raises(errors.ReviewWindowClosedError):
        write(checked_out=NOW - timedelta(days=REVIEW_WINDOW_DAYS + 1))


def test_the_last_day_of_the_window_still_counts() -> None:
    """Off-by-one on a boundary silently loses the reviews people write when
    the reminder email finally reaches them."""
    review = write(checked_out=NOW - timedelta(days=REVIEW_WINDOW_DAYS - 1))
    assert review.moderation is ModerationState.PUBLISHED


@pytest.mark.parametrize("rating", [0, 6, -1, 100])
def test_ratings_outside_one_to_five_are_refused(rating: int) -> None:
    """The aggregate is a running sum. A 100 that reaches it is not a rating
    anybody can find and delete afterwards — it is a permanently wrong average.
    """
    with pytest.raises(errors.InvalidRatingError):
        Rating(rating)


def test_a_body_too_short_to_say_anything_is_refused() -> None:
    """ "Great!" is a rating with extra steps. The minimum is what separates a
    review from a click."""
    with pytest.raises(errors.ReviewTooShortError):
        write(body="Great!")


# ══════════════════════════════════════════════════════════════════════════
# Editing
# ══════════════════════════════════════════════════════════════════════════


def test_the_author_may_edit_within_the_window() -> None:
    review = write()
    review.edit(
        rating=3, title="Revised", body=LONG_ENOUGH, categories=None, now=NOW + timedelta(hours=2)
    )

    assert int(review.rating) == 3
    assert review.edited_at is not None, "an edited review must say so"


def test_editing_closes_after_the_window() -> None:
    """An open-ended edit window is a review that can be sold.

    Leave it open and a host can offer a refund next year in exchange for a
    rewrite, against a page that has already earned its bookings.
    """
    review = write()
    with pytest.raises(errors.ReviewLockedError):
        review.edit(
            rating=1,
            title=None,
            body=LONG_ENOUGH,
            categories=None,
            now=NOW + EDIT_WINDOW + timedelta(minutes=1),
        )


def test_a_reply_freezes_the_review() -> None:
    """Otherwise the guest rewrites the review and the host's answer, still
    published underneath, now appears to respond to something nobody said."""
    review = write()
    review.reply(
        body="We are sorry about the lane — we have since fitted glazing.",
        now=NOW,
        vendor_id=VENDOR,
    )

    with pytest.raises(errors.ReviewLockedError):
        review.edit(
            rating=1,
            title=None,
            body=LONG_ENOUGH,
            categories=None,
            now=NOW + timedelta(minutes=5),
        )


def test_only_one_reply() -> None:
    """A review page that becomes an argument helps nobody reading it."""
    review = write()
    review.reply(body="Thank you for the note.", now=NOW, vendor_id=VENDOR)

    with pytest.raises(errors.ReviewLockedError):
        review.reply(body="Also, one more thing.", now=NOW + timedelta(minutes=1), vendor_id=VENDOR)


def test_another_vendor_cannot_reply_on_a_host_behalf() -> None:
    """The reply is signed by the property. Anyone who can post one can put
    words in a business's mouth on a page it does not control."""
    review = write()
    with pytest.raises(errors.ReviewAccessDeniedError):
        review.reply(body="Speaking for a property I do not own.", now=NOW, vendor_id=uuid.uuid4())


# ══════════════════════════════════════════════════════════════════════════
# Moderation
#
# The asymmetry here is deliberate and is the whole point of the module.
# ══════════════════════════════════════════════════════════════════════════


def test_flagging_does_not_hide_the_review() -> None:
    """**The** rule this module exists to enforce.

    If objecting to a review suppressed it, every critical review would be
    objected to and the rating would mean nothing. A flag raises it with staff
    and changes nothing a reader sees.
    """
    review = write(rating=1)
    review.flag(reason="The guest never stayed — the booking was cancelled.")

    assert review.moderation is ModerationState.FLAGGED
    assert review.counts_towards_rating, "a flag must not quietly remove the score"
    assert review.is_visible, "a flag must not quietly hide the text"


def test_removal_needs_a_reason() -> None:
    """Someone will be asked, months later, why a paying guest's review
    disappeared. "No reason recorded" is not an answer."""
    review = write()
    with pytest.raises(errors.ModerationReasonRequiredError):
        review.remove(reason="   ", now=NOW)


def test_removal_hides_it_and_stops_it_counting() -> None:
    review = write(rating=1)
    review.remove(reason="Contains a phone number.", now=NOW)

    assert review.moderation is ModerationState.REMOVED
    assert not review.is_visible
    assert not review.counts_towards_rating


def test_a_removed_review_can_be_reinstated() -> None:
    """Moderation gets it wrong. A one-way door means the only safe moderation
    decision is to do nothing."""
    review = write()
    review.remove(reason="Reported as fake.", now=NOW)
    review.restore()

    assert review.moderation is ModerationState.PUBLISHED
    assert review.counts_towards_rating


def test_flagging_a_removed_review_does_not_republish_it() -> None:
    """A host flagging a review staff already took down must not walk it back
    into public view through a side door."""
    review = write()
    review.remove(reason="Contains a phone number.", now=NOW)
    review.flag(reason="I disagree with this review.")

    assert review.moderation is ModerationState.REMOVED
    assert not review.is_visible
