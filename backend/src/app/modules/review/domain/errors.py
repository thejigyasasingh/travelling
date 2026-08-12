"""Review errors."""

from __future__ import annotations

from app.shared.domain.errors import BusinessRuleViolationError, DomainError


class InvalidRatingError(BusinessRuleViolationError):
    code = "REVIEW_RATING_INVALID"

    def __init__(self, value: int) -> None:
        super().__init__("A rating must be a whole number from 1 to 5.", details={"value": value})


class ReviewTooShortError(BusinessRuleViolationError):
    code = "REVIEW_TOO_SHORT"

    def __init__(self, minimum: int) -> None:
        super().__init__(
            f"Tell future guests a little more — at least {minimum} characters.",
            details={"minimum": minimum},
        )


class ReviewWindowClosedError(BusinessRuleViolationError):
    """Too long after the stay.

    Beyond the window a review says more about the interval than the stay, and
    a host has no realistic way to answer it.
    """

    code = "REVIEW_WINDOW_CLOSED"

    def __init__(self, days: int) -> None:
        super().__init__(f"Reviews close {days} days after checkout.", details={"days": days})


class ReviewLockedError(BusinessRuleViolationError):
    code = "REVIEW_LOCKED"

    def __init__(self, because: str) -> None:
        super().__init__(f"This review cannot be changed — {because}.")


class StayNotCompletedError(BusinessRuleViolationError):
    """The rule that makes reviews worth reading.

    A review platform where anyone can post is one nobody believes, and forged
    reviews are what competitors buy by the thousand.
    """

    code = "REVIEW_STAY_NOT_COMPLETED"

    def __init__(self) -> None:
        super().__init__("You can review a stay once it is complete.")


class AlreadyReviewedError(BusinessRuleViolationError):
    code = "REVIEW_ALREADY_EXISTS"

    def __init__(self) -> None:
        super().__init__("You have already reviewed this stay.")


class ModerationReasonRequiredError(BusinessRuleViolationError):
    code = "REVIEW_MODERATION_REASON_REQUIRED"

    def __init__(self) -> None:
        super().__init__("Removing a review needs a reason on the record.")


class ReviewNotFoundError(DomainError):
    code = "REVIEW_NOT_FOUND"
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Review not found.")


class ReviewAccessDeniedError(DomainError):
    """Not this vendor's property, or not this guest's review.

    404, not 403 — a distinguishable refusal confirms the review exists.
    """

    code = "REVIEW_NOT_FOUND"
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Review not found.")
