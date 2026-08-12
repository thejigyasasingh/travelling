"""Coupon errors.

Each one is distinct because each has a different thing a guest can do about
it: wait, spend more, use a different code, or give up. Collapsing them into
"invalid coupon" is what makes a checkout feel broken.
"""

from __future__ import annotations

from datetime import datetime

from app.shared.domain.errors import BusinessRuleViolationError, DomainError


class InvalidCouponError(BusinessRuleViolationError):
    code = "COUPON_INVALID"

    def __init__(self, field: str, problem: str) -> None:
        super().__init__(f"{field.replace('_', ' ')} {problem}.", details={"field": field})


class CouponNotFoundError(DomainError):
    code = "COUPON_NOT_FOUND"
    status_code = 404

    def __init__(self, code_value: str | None = None) -> None:
        super().__init__(
            "That code was not recognised.",
            details={"code": code_value} if code_value else {},
        )


class CouponNotActiveError(BusinessRuleViolationError):
    code = "COUPON_NOT_ACTIVE"

    def __init__(self, code_value: str, status: str) -> None:
        super().__init__(
            "That code is no longer available.",
            details={"code": code_value, "status": status},
        )


class CouponExpiredError(BusinessRuleViolationError):
    code = "COUPON_EXPIRED"

    def __init__(self, code_value: str, ended_at: datetime) -> None:
        super().__init__(
            "That code expired.",
            details={"code": code_value, "ended_at": ended_at.isoformat()},
        )


class CouponNotYetValidError(BusinessRuleViolationError):
    code = "COUPON_NOT_YET_VALID"

    def __init__(self, code_value: str, starts_at: datetime) -> None:
        super().__init__(
            "That code is not active yet.",
            details={"code": code_value, "starts_at": starts_at.isoformat()},
        )


class CouponExhaustedError(BusinessRuleViolationError):
    code = "COUPON_EXHAUSTED"

    def __init__(self, code_value: str) -> None:
        super().__init__("That code has been fully claimed.", details={"code": code_value})


class CouponAlreadyUsedError(BusinessRuleViolationError):
    code = "COUPON_ALREADY_USED"

    def __init__(self, code_value: str, limit: int) -> None:
        super().__init__(
            "You have already used that code."
            if limit == 1
            else f"That code can be used {limit} times per guest, and you have used it.",
            details={"code": code_value, "per_user_limit": limit},
        )


class CouponMinimumNotMetError(BusinessRuleViolationError):
    code = "COUPON_MINIMUM_NOT_MET"

    def __init__(self, code_value: str, minimum_minor: int) -> None:
        super().__init__(
            "This booking is below the minimum for that code.",
            details={"code": code_value, "minimum_minor": minimum_minor},
        )


class CouponFirstBookingOnlyError(BusinessRuleViolationError):
    code = "COUPON_FIRST_BOOKING_ONLY"

    def __init__(self, code_value: str) -> None:
        super().__init__("That code is for a first booking only.", details={"code": code_value})


class CouponNotApplicableError(BusinessRuleViolationError):
    code = "COUPON_NOT_APPLICABLE"

    def __init__(self, code_value: str) -> None:
        super().__init__("That code does not apply to this stay.", details={"code": code_value})


class DuplicateCouponCodeError(BusinessRuleViolationError):
    code = "COUPON_CODE_TAKEN"

    def __init__(self, code_value: str) -> None:
        super().__init__(
            f"A coupon with the code {code_value} already exists.",
            details={"code": code_value},
        )
