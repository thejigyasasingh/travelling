"""Webhook handling — the authoritative payment path.

Four properties this has to hold, and each corresponds to something Razorpay
actually does:

**Signature first, parse second.** Everything in the request is
attacker-controlled until the HMAC over the raw body checks out. A forged
``payment.captured`` is a free booking.

**Idempotent.** Razorpay redelivers on any non-2xx, and duplicates arrive even
after a 200. Every delivery is claimed by ``x-razorpay-event-id`` before any
side effect runs.

**Order-independent.** ``payment.captured`` routinely arrives before
``payment.authorized``. Every transition is non-strict here: a stale event is
ignored, not applied, and never rejected — rejecting it makes Razorpay redeliver
it forever.

**Always answer 200 once accepted.** A handler that raises on a business
condition it has already recorded gets the same event redelivered until
Razorpay gives up, and by then the retries have buried the real failures.

Delivery is at-least-once, never exactly-once. The dedupe store plus forward-only
transitions is what turns that into exactly-once *effect*.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Final

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.types.money import Money
from app.modules.booking.public import BookingPaymentService
from app.modules.payment.application.dto import WebhookInput
from app.modules.payment.application.ports import (
    GatewayPayment,
    PaymentGateway,
    PaymentRepository,
    WebhookEventStore,
)
from app.modules.payment.application.use_cases.checkout import apply_gateway_state
from app.modules.payment.domain import errors
from app.modules.payment.domain.value_objects import PaymentMethod
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

#: Events we act on. Anything else is acknowledged and dropped — Razorpay sends
#: dozens of event types, and subscribing to one we do not handle must not
#: produce an error every time it fires.
HANDLED_EVENTS: Final = frozenset(
    {
        "payment.authorized",
        "payment.captured",
        "payment.failed",
        "refund.processed",
        "refund.failed",
        "payment.dispute.created",
        "order.paid",
    }
)


@dataclass(slots=True)
class ProcessWebhookUseCase:
    payments: PaymentRepository
    bookings: BookingPaymentService
    events: WebhookEventStore
    gateway: PaymentGateway
    clock: Clock

    async def execute(self, data: WebhookInput, actor: Actor) -> dict[str, Any]:
        now = self.clock.now()

        # 1. Signature over the RAW bytes. Nothing below runs until this passes.
        self.gateway.verify_webhook_signature(raw_body=data.raw_body, signature=data.signature)

        event_type = str(data.payload.get("event", ""))

        # 2. Claim the delivery. Atomic — two workers receiving the same
        #    redelivery cannot both proceed.
        claimed = await self.events.claim(
            event_id=data.event_id,
            event_type=event_type,
            payload=data.payload,
            now=now,
        )
        if not claimed:
            logger.info("webhook_duplicate", event_id=data.event_id, event_type=event_type)
            return {"status": "duplicate", "event": event_type}

        if event_type not in HANDLED_EVENTS:
            await self.events.mark_processed(data.event_id, now=now)
            logger.info("webhook_ignored", event_id=data.event_id, event_type=event_type)
            return {"status": "ignored", "event": event_type}

        try:
            result = await self._dispatch(event_type, data.payload, now)
        except Exception as exc:
            # Recorded so the reconciliation job can find it, then re-raised so
            # the handler answers 5xx and Razorpay retries. Only genuine
            # failures reach here — business conditions are handled inside.
            await self.events.mark_failed(data.event_id, error=str(exc), now=now)
            logger.error(
                "webhook_processing_failed",
                event_id=data.event_id,
                event_type=event_type,
                error=str(exc),
            )
            raise

        await self.events.mark_processed(data.event_id, now=now)
        logger.info(
            "webhook_processed",
            event_id=data.event_id,
            event_type=event_type,
            outcome=result.get("status"),
        )
        return result

    # ── dispatch ──────────────────────────────────────────────────────────

    async def _dispatch(
        self, event_type: str, payload: dict[str, Any], now: object
    ) -> dict[str, Any]:
        entity = _entity(payload)

        if event_type in ("payment.authorized", "payment.captured", "payment.failed"):
            return await self._on_payment(entity, now)
        if event_type == "order.paid":
            # Fires alongside payment.captured. Handled for the case where the
            # payment event is lost — the order event is enough to reconcile.
            return await self._on_order_paid(payload, now)
        if event_type in ("refund.processed", "refund.failed"):
            return await self._on_refund(
                entity, succeeded=event_type.endswith("processed"), now=now
            )
        if event_type == "payment.dispute.created":
            return await self._on_dispute(entity, payload, now)
        return {"status": "ignored"}  # pragma: no cover — guarded by HANDLED_EVENTS

    async def _on_payment(self, entity: dict[str, Any], now: object) -> dict[str, Any]:
        order_id = entity.get("order_id")
        payment = await self.payments.get_by_order_id(str(order_id)) if order_id else None
        if payment is None:
            payment = await self.payments.get_by_gateway_payment_id(str(entity.get("id", "")))
        if payment is None:
            # A payment for an order we do not have. Not fatal — it may belong
            # to another environment sharing the webhook endpoint — but it is
            # acknowledged rather than retried forever.
            logger.warning("webhook_for_unknown_order", order_id=order_id)
            return {"status": "unknown_order"}

        remote = _to_gateway_payment(entity)
        try:
            result = await apply_gateway_state(
                payment=payment,
                remote=remote,
                bookings=self.bookings,
                now=now,
                # Non-strict: out-of-order and redelivered events are normal.
                strict=False,
            )
        except errors.AmountMismatchError:
            # The gateway says an amount our booking does not agree with. Never
            # silently accepted — it means either tampering or a bug in our own
            # pricing, and both need a human.
            logger.error(
                "webhook_amount_mismatch",
                payment_id=str(payment.id),
                expected=payment.expected_amount.amount_minor,
                received=entity.get("amount"),
            )
            return {"status": "amount_mismatch", "payment_id": str(payment.id)}
        except Exception as exc:
            # A booking that cannot be confirmed — an expired hold, most often.
            # Recorded and acknowledged; the payment stays captured and the
            # reconciliation job raises it for refund.
            logger.warning(
                "webhook_confirm_failed",
                payment_id=str(payment.id),
                booking_id=str(payment.booking_id),
                error=str(exc),
            )
            return {"status": "confirm_failed", "payment_id": str(payment.id)}

        return {"status": result.status, "payment_id": str(payment.id)}

    async def _on_order_paid(self, payload: dict[str, Any], now: object) -> dict[str, Any]:
        order = (payload.get("payload", {}).get("order", {}) or {}).get("entity", {})
        payment_entity = (payload.get("payload", {}).get("payment", {}) or {}).get("entity", {})
        if not payment_entity:
            return {"status": "ignored"}
        payment_entity.setdefault("order_id", order.get("id"))
        return await self._on_payment(payment_entity, now)

    async def _on_refund(
        self, entity: dict[str, Any], *, succeeded: bool, now: object
    ) -> dict[str, Any]:
        gateway_payment_id = str(entity.get("payment_id", ""))
        payment = await self.payments.get_by_gateway_payment_id(gateway_payment_id)
        if payment is None:
            logger.warning("refund_webhook_unknown_payment", payment_id=gateway_payment_id)
            return {"status": "unknown_payment"}

        # Razorpay echoes our notes back, which is how the refund is matched to
        # the attempt we recorded — the gateway's own refund id is not known to
        # us until this moment.
        notes = entity.get("notes") or {}
        idempotency_key = str(notes.get("idempotency_key", "")) or _derive_key(payment.booking_id)

        if succeeded:
            payment.mark_refund_processed(
                idempotency_key=idempotency_key,
                gateway_refund_id=str(entity.get("id", "")),
                now=now,  # type: ignore[arg-type]
            )
            await self.bookings.record_refund_result(
                booking_id=payment.booking_id,
                succeeded=True,
                gateway_refund_id=str(entity.get("id", "")),
            )
        else:
            error = str(entity.get("error_description") or "refund failed at gateway")
            payment.mark_refund_failed(
                idempotency_key=idempotency_key,
                error=error,
                now=now,  # type: ignore[arg-type]
            )
            await self.bookings.record_refund_result(
                booking_id=payment.booking_id, succeeded=False, error=error
            )

        return {"status": "refund_recorded", "payment_id": str(payment.id)}

    async def _on_dispute(
        self, entity: dict[str, Any], payload: dict[str, Any], now: object
    ) -> dict[str, Any]:
        """A chargeback. The money is already gone.

        Recorded rather than acted on: the dispute has a response deadline and
        an evidence process that a human runs. What matters here is that the
        ledger reflects reality and that someone is alerted.
        """
        gateway_payment_id = str(entity.get("payment_id", ""))
        payment = await self.payments.get_by_gateway_payment_id(gateway_payment_id)
        if payment is None:
            return {"status": "unknown_payment"}

        amount = Money(
            int(entity.get("amount", payment.expected_amount.amount_minor)),
            str(entity.get("currency", payment.currency)),
        )
        payment.mark_disputed(
            amount=amount,
            now=now,  # type: ignore[arg-type]
            reason=str(entity.get("reason_code") or entity.get("reason_description") or ""),
        )
        logger.error(  # ERROR: a rising chargeback rate threatens card processing
            "payment_disputed",
            payment_id=str(payment.id),
            booking_reference=payment.booking_reference,
            amount_minor=amount.amount_minor,
        )
        return {"status": "dispute_recorded", "payment_id": str(payment.id)}


# ══════════════════════════════════════════════════════════════════════════


def _entity(payload: dict[str, Any]) -> dict[str, Any]:
    """Razorpay nests the interesting object under
    ``payload.<type>.entity``. Pulled out here so every handler sees the same
    flat shape regardless of which key it arrived under."""
    inner = payload.get("payload", {}) or {}
    for key in ("payment", "refund", "order", "dispute"):
        section = inner.get(key)
        if isinstance(section, dict) and "entity" in section:
            entity: dict[str, Any] = section["entity"]
            return entity
    return {}


def _to_gateway_payment(entity: dict[str, Any]) -> GatewayPayment:
    """Webhook entity → the same shape ``fetch_payment`` returns.

    So the webhook path and the checkout path share one state-application
    function and cannot drift about what "captured" means.
    """
    currency = str(entity.get("currency", "INR"))
    method = PaymentMethod.parse(entity.get("method"))

    identifier = None
    if method is PaymentMethod.UPI:
        identifier = entity.get("vpa")
    elif method is PaymentMethod.CARD:
        identifier = (entity.get("card") or {}).get("last4")

    return GatewayPayment(
        id=str(entity.get("id", "")),
        order_id=str(entity["order_id"]) if entity.get("order_id") else None,
        amount=Money(int(entity.get("amount", 0)), currency),
        status=str(entity.get("status", "")),
        method=method,
        captured=bool(entity.get("captured", False)),
        fee=Money(int(entity["fee"]), currency) if entity.get("fee") else None,
        tax=Money(int(entity["tax"]), currency) if entity.get("tax") else None,
        vpa_or_last4=str(identifier) if identifier else None,
        error_code=str(entity["error_code"]) if entity.get("error_code") else None,
        error_description=(
            str(entity["error_description"]) if entity.get("error_description") else None
        ),
        raw=entity,
    )


def _derive_key(booking_id: uuid.UUID) -> str:
    """Fallback when Razorpay does not echo our notes.

    Matches the key the booking module generates, so a refund initiated there
    is still matched to the right attempt.
    """
    return f"refund-{booking_id}"
