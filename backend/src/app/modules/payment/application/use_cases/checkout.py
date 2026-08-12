"""Creating an order, and verifying what comes back.

The flow, and why each step exists:

1. **Create an order.** The guest's booking is already holding inventory; this
   creates the Razorpay order the browser's checkout will reference.
2. The browser pays, and Razorpay hands it ``order_id``, ``payment_id`` and a
   ``signature``.
3. **Verify.** The signature proves the payment belongs to that order — but not
   what it was worth, and not that the money was actually captured. So the
   gateway is then asked directly, and the amount is checked against the
   booking.

Step 3's belt-and-braces is deliberate. A valid signature only means "Razorpay
issued this pair"; a client could still replay a genuine ₹1 payment from a
different order it also owns. Fetching the payment and comparing the amount is
what closes that.

**The webhook is the authority, not this path.** A client can close the tab
before the callback fires. This route exists so the guest sees a confirmation
immediately rather than staring at a spinner until a webhook lands; the webhook
reconciles either way, and both are idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.types.money import Money
from app.modules.booking.public import BookingPaymentService
from app.modules.payment.application.dto import (
    CheckoutSession,
    CreateOrderInput,
    PaymentResult,
    VerifyCheckoutInput,
)
from app.modules.payment.application.ports import PaymentGateway, PaymentRepository
from app.modules.payment.domain import errors
from app.modules.payment.domain.entities import Payment
from app.modules.payment.domain.value_objects import PaymentMethod
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)

#: Attempts allowed per booking. Beyond this the guest almost certainly has a
#: real problem with their instrument, and repeated declines against the same
#: card are a fraud signal the gateway itself starts penalising us for.
MAX_ATTEMPTS: Final = 5


@dataclass(slots=True)
class CreateOrderUseCase:
    payments: PaymentRepository
    bookings: BookingPaymentService
    gateway: PaymentGateway
    clock: Clock

    async def execute(self, data: CreateOrderInput, actor: Actor) -> CheckoutSession:
        booking = await self.bookings.snapshot(data.booking_id)
        if booking is None:
            raise EntityNotFoundError("Booking", data.booking_id)
        if actor.user_id != booking.guest_id and not actor.has_role("admin", "support"):
            # Not this guest's booking. 404 at the interface, so the endpoint
            # cannot be used to probe which booking ids exist.
            raise errors.PaymentAccessDeniedError
        if not booking.is_payable:
            raise errors.BookingNotPayableError(booking.status)

        # A guest opening checkout in two tabs must not produce two live
        # orders for one booking — the second payment would have nothing to
        # confirm and would need refunding.
        existing = await self.payments.get_active_for_booking(booking.id)
        if existing is not None:
            logger.info(
                "checkout_session_reused",
                booking_id=str(booking.id),
                payment_id=str(existing.id),
            )
            return self._session(existing, booking)

        attempts = await self.payments.count_attempts(booking.id)
        if attempts >= MAX_ATTEMPTS:
            raise errors.RetryNotAllowedError("too_many_attempts")

        order = await self.gateway.create_order(
            amount=booking.amount,
            # The booking reference, so a payment can be matched to a booking
            # from the Razorpay dashboard during an incident.
            receipt=booking.reference,
            notes={
                "booking_id": str(booking.id),
                "booking_reference": booking.reference,
                "property": booking.property_name[:40],
            },
        )

        payment = Payment.create_order(
            booking_id=booking.id,
            booking_reference=booking.reference,
            guest_id=booking.guest_id,
            amount=booking.amount,
            gateway_order_id=order.id,
            attempt_number=attempts + 1,
        )
        await self.payments.add(payment)

        logger.info(
            "payment_order_created",
            payment_id=str(payment.id),
            booking_id=str(booking.id),
            order_id=order.id,
            amount_minor=booking.amount.amount_minor,
            attempt=payment.attempt_number,
        )
        return self._session(payment, booking)

    def _session(self, payment: Payment, booking: object) -> CheckoutSession:
        b = booking  # narrowed by the caller
        expires_in = None
        if b.hold_expires_at is not None:  # type: ignore[attr-defined]
            remaining = (b.hold_expires_at - self.clock.now()).total_seconds()  # type: ignore[attr-defined]
            expires_in = max(0, int(remaining))

        return CheckoutSession(
            payment_id=payment.id,
            gateway_order_id=payment.gateway_order_id,
            key_id=self.gateway.public_key,
            amount_minor=payment.expected_amount.amount_minor,
            currency=payment.currency,
            booking_reference=payment.booking_reference,
            prefill_name=b.guest_name,  # type: ignore[attr-defined]
            prefill_email=b.guest_email,  # type: ignore[attr-defined]
            prefill_contact=b.guest_phone,  # type: ignore[attr-defined]
            property_name=b.property_name,  # type: ignore[attr-defined]
            expires_in=expires_in,
            attempt_number=payment.attempt_number,
            notes={"booking_reference": payment.booking_reference},
        )


@dataclass(slots=True)
class VerifyCheckoutUseCase:
    """Verify the browser's callback and confirm the booking."""

    payments: PaymentRepository
    bookings: BookingPaymentService
    gateway: PaymentGateway
    clock: Clock

    async def execute(self, data: VerifyCheckoutInput, actor: Actor) -> PaymentResult:
        now = self.clock.now()

        # 1. Signature. Raises before anything else happens — everything in the
        #    request is attacker-controlled until this passes.
        self.gateway.verify_checkout_signature(
            order_id=data.razorpay_order_id,
            payment_id=data.razorpay_payment_id,
            signature=data.razorpay_signature,
        )

        payment = await self.payments.get_by_order_id(data.razorpay_order_id)
        if payment is None:
            # A valid signature for an order we never created means our
            # key_secret is being used elsewhere, or the order belongs to a
            # different environment. Loud, because neither is normal.
            logger.error("checkout_for_unknown_order", order_id=data.razorpay_order_id)
            raise errors.PaymentNotFoundError(data.razorpay_order_id)

        payment.assert_visible_to(
            user_id=actor.user_id, is_staff=actor.has_role("admin", "support")
        )

        # 2. Ask the gateway what actually happened. The signature proves the
        #    pair is genuine; only this proves the amount and that the money
        #    was captured rather than merely authorised.
        remote = await self.gateway.fetch_payment(data.razorpay_payment_id)

        if remote.order_id and remote.order_id != payment.gateway_order_id:
            # A genuine payment from a *different* order, replayed here.
            logger.error(
                "payment_order_mismatch",
                expected=payment.gateway_order_id,
                received=remote.order_id,
            )
            raise errors.SignatureVerificationError("order_mismatch")

        return await apply_gateway_state(
            payment=payment,
            remote=remote,
            bookings=self.bookings,
            now=now,
            strict=True,
        )


async def apply_gateway_state(
    *,
    payment: Payment,
    remote: object,
    bookings: BookingPaymentService,
    now: object,
    strict: bool,
) -> PaymentResult:
    """Fold the gateway's view into ours, and confirm the booking if paid.

    Shared by the checkout callback and the webhook handler so the two cannot
    drift — they are the same decision arriving by two routes, and a second
    implementation would eventually disagree with the first about what
    "captured" means.

    ``strict=False`` for webhooks: an out-of-order or redelivered event is
    normal traffic and must still be acknowledged with a 200, or Razorpay
    redelivers it forever.
    """
    r = remote  # typed loosely so both call sites can pass their own shape
    invoice_number: str | None = None
    booking_status: str | None = None

    if r.status == "failed" or r.error_code:  # type: ignore[attr-defined]
        payment.mark_failed(
            code=r.error_code,  # type: ignore[attr-defined]
            reason=r.error_description,  # type: ignore[attr-defined]
            now=now,  # type: ignore[arg-type]
            gateway_payment_id=r.id,  # type: ignore[attr-defined]
            strict=strict,
        )
        logger.info(
            "payment_failed",
            payment_id=str(payment.id),
            code=r.error_code,  # type: ignore[attr-defined]
        )

    elif r.captured or r.status == "captured":  # type: ignore[attr-defined]
        payment.mark_captured(
            gateway_payment_id=r.id,  # type: ignore[attr-defined]
            amount=r.amount,  # type: ignore[attr-defined]
            method=r.method,  # type: ignore[attr-defined]
            now=now,  # type: ignore[arg-type]
            fee=r.fee,  # type: ignore[attr-defined]
            tax=r.tax,  # type: ignore[attr-defined]
            vpa_or_last4=r.vpa_or_last4,  # type: ignore[attr-defined]
            strict=strict,
        )
        # Money has moved, so the booking can be confirmed. Same transaction:
        # a captured payment against an unconfirmed booking is the worst
        # available outcome — the guest has paid and has no reservation.
        invoice_number = await bookings.confirm_paid(
            booking_id=payment.booking_id,
            payment_id=r.id,  # type: ignore[attr-defined]
            paid_amount=r.amount,  # type: ignore[attr-defined]
        )
        booking_status = "confirmed"

    elif r.status == "authorized":  # type: ignore[attr-defined]
        # Funds reserved, not taken. The booking is deliberately NOT confirmed
        # here — an authorisation that is never captured reverses silently.
        payment.mark_authorized(
            gateway_payment_id=r.id,  # type: ignore[attr-defined]
            amount=r.amount,  # type: ignore[attr-defined]
            method=r.method,  # type: ignore[attr-defined]
            now=now,  # type: ignore[arg-type]
            vpa_or_last4=r.vpa_or_last4,  # type: ignore[attr-defined]
            strict=strict,
        )

    return PaymentResult(
        payment_id=payment.id,
        status=payment.status.value,
        booking_id=payment.booking_id,
        booking_reference=payment.booking_reference,
        amount_minor=payment.expected_amount.amount_minor,
        currency=payment.currency,
        method=(payment.method or PaymentMethod.UNKNOWN).value,
        invoice_number=invoice_number,
        booking_status=booking_status,
        gateway_payment_id=payment.gateway_payment_id,
    )


def money_or_none(minor: int | None, currency: str) -> Money | None:
    return Money(minor, currency) if minor is not None else None
