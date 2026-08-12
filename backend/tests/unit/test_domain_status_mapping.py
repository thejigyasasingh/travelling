"""How a domain error becomes an HTTP status.

The table used to be keyed by exact type, so every module-specific error fell
through to the 409 default. That looked harmless because most of them *are*
409 — and it silently broke the ones that are not, including two that document
themselves as 404 specifically so the endpoint is not an enumeration oracle.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.interface.api.exception_handlers import _resolve_domain_status
from app.modules.booking.domain import errors as booking_errors
from app.modules.payment.domain import errors as payment_errors
from app.shared.domain.errors import (
    BusinessRuleViolationError,
    DomainError,
    EntityNotFoundError,
)

pytestmark = pytest.mark.unit


def test_a_subclass_inherits_its_mapping() -> None:
    """The actual bug: an exact-type lookup missed every subclass.

    A ``DatesUnavailableError`` is a ``BusinessRuleViolationError``; before the
    MRO walk it reached the default instead of its mapping. That happened to be
    the same 409, which is precisely why nobody noticed.
    """
    status, _ = _resolve_domain_status(booking_errors.DatesUnavailableError([date(2026, 9, 12)]))
    assert status == 409


def test_a_not_found_subclass_is_404_not_409() -> None:
    class MissingThingError(EntityNotFoundError):
        pass

    status, _ = _resolve_domain_status(MissingThingError("Thing", "abc"))
    assert status == 404


def test_an_explicit_status_wins() -> None:
    """Modules use this to say what the generic table cannot."""
    status, level = _resolve_domain_status(payment_errors.PaymentsDisabledError())
    assert status == 503
    # 5xx is our problem, so it is logged as an error rather than info.
    assert level == "error"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        # Not "403 forbidden": distinguishing "not yours" from "does not exist"
        # is what lets someone enumerate payments and bookings by trying ids.
        (payment_errors.PaymentAccessDeniedError(), 404),
        (booking_errors.BookingAccessDeniedError(), 404),
        (payment_errors.PaymentNotFoundError("abc"), 404),
        # A forged signature is an authentication failure, not a conflict.
        (payment_errors.SignatureVerificationError(), 401),
        # Not our bug, usually transient, worth retrying.
        (payment_errors.GatewayError("upstream refused"), 503),
    ],
)
def test_errors_answer_the_status_their_docstrings_promise(
    error: DomainError, expected: int
) -> None:
    status, _ = _resolve_domain_status(error)
    assert status == expected


def test_an_unmapped_error_defaults_to_conflict() -> None:
    class OddError(DomainError):
        code = "ODD"

    status, _ = _resolve_domain_status(OddError("odd"))
    assert status == 409


def test_a_plain_business_rule_violation_is_409() -> None:
    status, _ = _resolve_domain_status(BusinessRuleViolationError("nope"))
    assert status == 409
