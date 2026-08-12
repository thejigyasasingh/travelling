"""Refunds, retries and reconciliation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.types.money import Money
from app.modules.booking.public import BookingPaymentService
from app.modules.payment.application.dto import PaymentResult, RefundInput
from app.modules.payment.application.ports import PaymentGateway, PaymentRepository
from app.modules.payment.application.use_cases.checkout import apply_gateway_state
from app.modules.payment.domain import errors
from app.modules.payment.domain.value_objects import RefundSpeed
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)

#: Razorpay auto-reverses an authorisation that is not captured within ~5 days.
#: The job runs well inside that: a reversed authorisation leaves a confirmed
#: booking nobody was paid for, and the guest has already travelled.
CAPTURE_DEADLINE_HOURS: Final = 48

#: How long to wait for a webhook before asking the gateway directly. Webhooks
#: are "at least once", which occasionally means "never".
RECONCILE_AFTER_MINUTES: Final = 15


@dataclass(slots=True)
class IssueRefundUseCase:
    """Execute a refund against the gateway.

    Driven by ``RefundRequested`` from the booking module — booking never calls
    a gateway itself, which is what keeps the dependency one-way.

    Two guarantees hold it together: the refund attempt is recorded **before**
    the gateway call, and the idempotency key is derived from the booking id.
    So a process that dies mid-call leaves something to retry, and the retry
    reaches Razorpay with the same key and refunds once.
    """

    payments: PaymentRepository
    bookings: BookingPaymentService
    gateway: PaymentGateway
    clock: Clock

    async def execute(self, data: RefundInput, actor: Actor) -> PaymentResult:
        now = self.clock.now()
        payment = await self.payments.get(data.payment_id)
        if payment is None:
            raise EntityNotFoundError("Payment", data.payment_id)
        if not actor.has_role("admin", "support", "system"):
            payment.assert_visible_to(user_id=actor.user_id)

        amount = (
            Money(data.amount_minor, payment.currency)
            if data.amount_minor is not None
            else payment.refundable_amount
        )
        if not amount.is_positive:
            raise errors.RefundExceedsCapturedError(
                amount.amount_minor, payment.refundable_amount.amount_minor
            )

        idempotency_key = f"refund-{payment.booking_id}"

        # Recorded first. If the process dies after the gateway call but before
        # the commit, this row plus the same key make the retry safe. The
        # reverse order would leave money gone with nothing pointing at it.
        attempt = payment.request_refund(
            amount=amount,
            reason=data.reason,
            idempotency_key=idempotency_key,
            now=now,
            booking_id=payment.booking_id,
            speed=RefundSpeed(data.speed),
        )
        if attempt.is_settled:
            logger.info("refund_already_settled", payment_id=str(payment.id))
            return _result(payment)

        if payment.gateway_payment_id is None:
            # Nothing was ever captured — an unpaid hold that was cancelled.
            payment.mark_refund_processed(
                idempotency_key=idempotency_key, gateway_refund_id="no-payment", now=now
            )
            await self.bookings.record_refund_result(
                booking_id=payment.booking_id, succeeded=True, gateway_refund_id="no-payment"
            )
            return _result(payment)

        try:
            refund = await self.gateway.refund(
                payment_id=payment.gateway_payment_id,
                amount=amount,
                idempotency_key=idempotency_key,
                # Echoed back on the refund webhook, which is how that webhook
                # is matched to this attempt.
                notes={
                    "idempotency_key": idempotency_key,
                    "booking_id": str(payment.booking_id),
                },
                speed=RefundSpeed(data.speed),
            )
        except Exception as exc:
            payment.mark_refund_failed(idempotency_key=idempotency_key, error=str(exc), now=now)
            await self.bookings.record_refund_result(
                booking_id=payment.booking_id, succeeded=False, error=str(exc)
            )
            logger.error(
                "refund_gateway_failed",
                payment_id=str(payment.id),
                booking_reference=payment.booking_reference,
                amount_minor=amount.amount_minor,
                error=str(exc),
            )
            # Re-raised so the task retries with backoff. The FAILED status is
            # already persisted, so a permanent failure is visible to support
            # rather than lost.
            raise

        # Razorpay may return `pending` for a normal-speed refund — the money
        # is on its way but not settled. The refund webhook closes it out.
        if refund.status == "processed":
            payment.mark_refund_processed(
                idempotency_key=idempotency_key, gateway_refund_id=refund.id, now=now
            )
            await self.bookings.record_refund_result(
                booking_id=payment.booking_id, succeeded=True, gateway_refund_id=refund.id
            )
        else:
            attempt.gateway_refund_id = refund.id

        logger.info(
            "refund_issued",
            payment_id=str(payment.id),
            booking_reference=payment.booking_reference,
            amount_minor=amount.amount_minor,
            gateway_refund_id=refund.id,
            status=refund.status,
        )
        return _result(payment)


@dataclass(slots=True)
class RetryPaymentUseCase:
    """Let a guest try again after a decline.

    A **new order** every time, never a reused one. Razorpay orders are not
    designed to be paid twice: reusing one after a failure produces confusing
    dashboard state and, on some methods, a duplicate charge. A fresh order per
    attempt also keeps each try independently traceable when support has to
    reconstruct what the guest saw.
    """

    payments: PaymentRepository
    bookings: BookingPaymentService
    gateway: PaymentGateway
    clock: Clock

    async def execute(self, booking_id: uuid.UUID, actor: Actor) -> PaymentResult:
        booking = await self.bookings.snapshot(booking_id)
        if booking is None:
            raise EntityNotFoundError("Booking", booking_id)
        if actor.user_id != booking.guest_id and not actor.has_role("admin", "support"):
            raise errors.PaymentAccessDeniedError

        # The hold is what makes a retry meaningful. Once it lapses the rooms
        # are gone, and paying would produce a booking with no inventory.
        if not booking.is_payable:
            raise errors.BookingNotPayableError(booking.status)

        previous = await self.payments.get_active_for_booking(booking_id)
        if previous is not None:
            # Raises if it is already paid — retrying a successful payment
            # charges twice.
            previous.assert_can_retry()

        logger.info(
            "payment_retry_requested",
            booking_id=str(booking_id),
            previous_status=previous.status.value if previous else None,
        )
        # The caller creates the new order through CreateOrderUseCase; this
        # exists to hold the eligibility rules in one place rather than
        # duplicating them at the route.
        return PaymentResult(
            payment_id=previous.id if previous else uuid.uuid4(),
            status="retry_allowed",
            booking_id=booking_id,
            booking_reference=booking.reference,
            amount_minor=booking.amount.amount_minor,
            currency=booking.amount.currency,
            method="unknown",
        )


@dataclass(slots=True)
class CaptureAuthorizedUseCase:
    """Capture authorisations before they reverse.

    Only reachable when auto-capture is off. An authorisation left uncaptured
    silently reverses after a few days — and by then the guest may have already
    stayed.
    """

    payments: PaymentRepository
    bookings: BookingPaymentService
    gateway: PaymentGateway
    clock: Clock

    async def execute(self, limit: int, actor: Actor) -> int:
        now = self.clock.now()
        cutoff = now - timedelta(hours=CAPTURE_DEADLINE_HOURS)
        stale = await self.payments.find_stale_authorized(older_than=cutoff, limit=limit)

        captured = 0
        for payment in stale:
            if payment.gateway_payment_id is None:  # pragma: no cover
                continue
            try:
                remote = await self.gateway.capture(
                    payment.gateway_payment_id, payment.expected_amount
                )
                await apply_gateway_state(
                    payment=payment,
                    remote=remote,
                    bookings=self.bookings,
                    now=now,
                    strict=False,
                )
                captured += 1
            except Exception as exc:
                logger.error(
                    "capture_failed",
                    payment_id=str(payment.id),
                    booking_reference=payment.booking_reference,
                    error=str(exc),
                )

        if captured:
            logger.info("authorizations_captured", count=captured)
        return captured


@dataclass(slots=True)
class ReconcilePaymentsUseCase:
    """Ask the gateway about payments whose webhook never arrived.

    Webhooks are delivered at least once, which in practice sometimes means
    "eventually" and occasionally "never" — a misconfigured endpoint, an outage
    on either side, a deploy that returned 502 for five minutes. Without this,
    a guest who paid sits with an unconfirmed booking until they contact
    support.
    """

    payments: PaymentRepository
    bookings: BookingPaymentService
    gateway: PaymentGateway
    clock: Clock

    async def execute(self, limit: int, actor: Actor) -> int:
        now = self.clock.now()
        cutoff = now - timedelta(minutes=RECONCILE_AFTER_MINUTES)
        stuck = await self.payments.find_pending_reconciliation(older_than=cutoff, limit=limit)

        resolved = 0
        for payment in stuck:
            if payment.gateway_payment_id is None:
                # Never got as far as a payment attempt — the guest opened
                # checkout and closed it. Nothing to reconcile.
                continue
            try:
                remote = await self.gateway.fetch_payment(payment.gateway_payment_id)
                await apply_gateway_state(
                    payment=payment,
                    remote=remote,
                    bookings=self.bookings,
                    now=now,
                    strict=False,
                )
                resolved += 1
                logger.info(
                    "payment_reconciled",
                    payment_id=str(payment.id),
                    status=payment.status.value,
                )
            except Exception as exc:
                logger.warning("reconcile_failed", payment_id=str(payment.id), error=str(exc))

        if resolved:
            logger.info("payments_reconciled", count=resolved)
        return resolved


def _result(payment: object) -> PaymentResult:
    p = payment
    return PaymentResult(
        payment_id=p.id,  # type: ignore[attr-defined]
        status=p.status.value,  # type: ignore[attr-defined]
        booking_id=p.booking_id,  # type: ignore[attr-defined]
        booking_reference=p.booking_reference,  # type: ignore[attr-defined]
        amount_minor=p.expected_amount.amount_minor,  # type: ignore[attr-defined]
        currency=p.currency,  # type: ignore[attr-defined]
        method=p.method.value,  # type: ignore[attr-defined]
        gateway_payment_id=p.gateway_payment_id,  # type: ignore[attr-defined]
    )
