"""Payment domain errors."""

from __future__ import annotations

from typing import Any

from app.shared.domain.errors import BusinessRuleViolationError, DomainError


class SignatureVerificationError(DomainError):
    """A callback or webhook failed verification.

    Deliberately opaque and always logged at WARNING. A forged signature is
    someone attempting to confirm a booking without paying, and the response
    must not tell them which part of the forgery to fix.
    """

    code = "SIGNATURE_INVALID"
    #: 401. The request presented a credential and it did not check out; that
    #: is an authentication failure, not a business conflict.
    status_code = 401

    def __init__(self, context: str = "signature") -> None:
        super().__init__("We could not verify this payment.", details={"context": context})


class AmountMismatchError(BusinessRuleViolationError):
    """The gateway's amount is not the booking's amount.

    Either the client tampered with the checkout parameters, or our own pricing
    disagrees with the order we created. Both must stop here: confirming a
    ₹50,000 booking against a ₹1 payment is the single most damaging bug
    available in this module.
    """

    code = "PAYMENT_AMOUNT_MISMATCH"

    def __init__(self, expected_minor: int, received_minor: int, currency: str) -> None:
        super().__init__(
            "The payment amount does not match this booking.",
            details={
                "expected_minor": expected_minor,
                "received_minor": received_minor,
                "currency": currency,
            },
        )


class PaymentNotFoundError(DomainError):
    code = "PAYMENT_NOT_FOUND"
    status_code = 404

    def __init__(self, identifier: Any = None) -> None:
        super().__init__(
            "Payment not found.", details={"id": str(identifier)} if identifier else {}
        )


class PaymentAccessDeniedError(DomainError):
    """Not this guest's payment.

    404 at the interface, not 403 — confirming that a payment id exists lets
    someone enumerate transactions.
    """

    code = "PAYMENT_NOT_FOUND"
    #: 404, not 403 and not 409 — anything that distinguishes "not yours" from
    #: "does not exist" lets someone enumerate payments by trying ids.
    status_code = 404

    def __init__(self) -> None:
        super().__init__("Payment not found.")


class InvalidPaymentTransitionError(BusinessRuleViolationError):
    """Payment states only move forward.

    Webhooks arrive out of order routinely — ``payment.captured`` can land
    before ``payment.authorized``. Applying a stale transition would move a
    captured payment back to authorised, and the reconciliation job would then
    see money it thinks was never taken.
    """

    code = "INVALID_PAYMENT_TRANSITION"

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            f"A {current} payment cannot become {target}.",
            details={"current": current, "target": target},
        )


class BookingNotPayableError(BusinessRuleViolationError):
    """The booking is expired, cancelled or already paid."""

    code = "BOOKING_NOT_PAYABLE"

    def __init__(self, status: str) -> None:
        super().__init__(
            "This booking can no longer be paid for.", details={"booking_status": status}
        )


class PaymentAlreadyCapturedError(BusinessRuleViolationError):
    """Guards double capture, which is charging the guest twice."""

    code = "PAYMENT_ALREADY_CAPTURED"

    def __init__(self, payment_id: str) -> None:
        super().__init__(
            "This payment has already been captured.", details={"payment_id": payment_id}
        )


class RefundExceedsCapturedError(BusinessRuleViolationError):
    """Refunding more than was taken is the platform paying the guest.

    Guarded in the domain *and* by a database CHECK, because a support tool or
    a data fix does not go through the aggregate.
    """

    code = "REFUND_EXCEEDS_CAPTURED"

    def __init__(self, requested_minor: int, refundable_minor: int) -> None:
        super().__init__(
            "A refund cannot exceed the amount still refundable on this payment.",
            details={
                "requested_minor": requested_minor,
                "refundable_minor": refundable_minor,
            },
        )


class GatewayError(DomainError):
    """Razorpay refused or was unreachable.

    503, not 500: it is not our bug, it is usually transient, and the client
    should retry rather than report it.
    """

    code = "PAYMENT_GATEWAY_ERROR"
    #: 503, as the docstring says: not our bug, usually transient, retryable.
    status_code = 503

    def __init__(self, message: str | None = None, *, gateway_code: str | None = None) -> None:
        super().__init__(
            message or "The payment provider is temporarily unavailable. Please try again.",
            details={"gateway_code": gateway_code} if gateway_code else {},
        )


class PaymentDeclinedError(BusinessRuleViolationError):
    """The bank said no.

    Distinct from :class:`GatewayError`: retrying the same card will fail
    again, so the guest needs a different method rather than a retry button.
    The gateway's own description is passed through — "insufficient funds" is
    actionable in a way that "payment failed" is not.
    """

    code = "PAYMENT_DECLINED"

    def __init__(self, reason: str | None = None, *, gateway_code: str | None = None) -> None:
        super().__init__(
            reason or "The payment was declined. Please try a different method.",
            details={"gateway_code": gateway_code} if gateway_code else {},
        )


class RetryNotAllowedError(BusinessRuleViolationError):
    code = "PAYMENT_RETRY_NOT_ALLOWED"

    def __init__(self, reason: str) -> None:
        super().__init__("This payment cannot be retried.", details={"reason": reason})


class DuplicateWebhookError(DomainError):
    """This event has already been processed.

    Not an error condition — Razorpay redelivers on any non-2xx, and a
    redelivery is expected. It exists so the handler can return 200 quickly
    without re-running side effects.
    """

    code = "WEBHOOK_ALREADY_PROCESSED"

    def __init__(self, event_id: str) -> None:
        super().__init__("Event already processed.", details={"event_id": event_id})


class PaymentsDisabledError(DomainError):
    """No gateway configured for this deployment."""

    code = "PAYMENTS_DISABLED"
    status_code = 503

    def __init__(self) -> None:
        super().__init__("Payments are not available right now.")
