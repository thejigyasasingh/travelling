"""Review value objects."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from app.modules.review.domain import errors

#: The sub-scores a guest may give. Fixed rather than free-form, so "cleanliness
#: 4.2 across 180 stays" is a number that means the same thing everywhere.
RATING_CATEGORIES: Final = (
    "cleanliness",
    "accuracy",
    "location",
    "value",
    "communication",
    "check_in",
)

MIN_RATING: Final = 1
MAX_RATING: Final = 5


class Rating(int):
    """An integer from 1 to 5.

    A subclass of `int` so it arithmetics like one — averaging is the whole
    point — while refusing to exist outside the range. A rating of 0 or 7
    reaching the database silently skews every aggregate computed from it.
    """

    __slots__ = ()

    def __new__(cls, value: int) -> Rating:
        number = int(value)
        if not MIN_RATING <= number <= MAX_RATING:
            raise errors.InvalidRatingError(number)
        return super().__new__(cls, number)


class ModerationState(StrEnum):
    PUBLISHED = "published"
    #: Disputed by the host and awaiting a human. Deliberately still visible and
    #: still counted — see `Review.flag`.
    FLAGGED = "flagged"
    #: Taken down and no longer counted.
    REMOVED = "removed"
