"""Payment HTTP endpoints.

The webhook route is the security-critical one, and it is unusual in three
ways that are all deliberate:

* **It reads the raw body**, not the parsed JSON. Re-serialising changes the
  bytes and the HMAC will not match — see ``domain/signature.py``.
* **It is exempt from rate limiting.** A throttled webhook makes Razorpay retry
  and eventually give up on a real payment.
* **It answers 200 for anything it has already handled**, including duplicates
  and events it ignores. A non-2xx makes Razorpay redeliver, and a handler that
  errors on normal traffic buries the real failures under retries.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

import orjson
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.core.serialization import dto_dict
from app.interface.api.deps import ActorDep
from app.modules.auth.domain.rbac import Permission
from app.modules.auth.interface.permissions import RequirePermission
from app.modules.payment.application import dto
from app.modules.payment.application.use_cases.checkout import (
    CreateOrderUseCase,
    VerifyCheckoutUseCase,
)
from app.modules.payment.application.use_cases.history import (
    GetPaymentUseCase,
    ListPaymentsUseCase,
)
from app.modules.payment.application.use_cases.refunds import (
    IssueRefundUseCase,
    RetryPaymentUseCase,
)
from app.modules.payment.application.use_cases.webhooks import ProcessWebhookUseCase
from app.modules.payment.interface import deps
from app.modules.payment.interface.schemas import (
    CheckoutSessionResponse,
    CreateOrderRequest,
    PaymentListResponse,
    PaymentResponse,
    PaymentResultResponse,
    RefundRequest,
    VerifyCheckoutRequest,
    WebhookAck,
)
from app.shared.application.use_case import Actor

logger = get_logger(__name__)

#: Webhooks are unauthenticated by design — the signature *is* the
#: authentication. The actor is the system, so audit logs distinguish a
#: gateway-driven confirmation from a support agent's.
_WEBHOOK_ACTOR = Actor.system()

router = APIRouter(prefix="/payments", tags=["payments"])
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])
admin_router = APIRouter(prefix="/admin/payments", tags=["admin: payments"])

CanRefund = Depends(RequirePermission(Permission.PAYMENT_REFUND_ANY))
CanReadAny = Depends(RequirePermission(Permission.PAYMENT_READ_ANY))


# ══════════════════════════════════════════════════════════════════════════
# Checkout
# ══════════════════════════════════════════════════════════════════════════


@router.post(
    "/orders",
    status_code=status.HTTP_201_CREATED,
    response_model=CheckoutSessionResponse,
    summary="Start checkout for a booking",
    responses={
        409: {"description": "Booking is expired, cancelled or already paid"},
        503: {"description": "Payments are not configured, or the gateway is down"},
    },
)
async def create_order(
    body: CreateOrderRequest,
    actor: ActorDep,
    use_case: Annotated[CreateOrderUseCase, Depends(deps.create_order_uc)],
) -> CheckoutSessionResponse:
    """Create the Razorpay order the client's checkout will reference.

    Returns `key_id` — the **public** merchant identifier, which authorises
    nothing on its own. The secret never leaves the server, which is why
    signature verification happens in `/verify` rather than in the browser.

    Calling this twice for one booking returns the **same** order rather than
    creating a second: two live orders for one booking means a second payment
    with nothing to confirm and a refund to issue.
    """
    session = await use_case.execute(dto.CreateOrderInput(booking_id=body.booking_id), actor)
    return CheckoutSessionResponse(**dto_dict(session))


@router.post(
    "/verify",
    response_model=PaymentResultResponse,
    summary="Verify a completed checkout",
    responses={
        401: {"description": "Signature verification failed"},
        409: {"description": "The amount does not match the booking"},
    },
)
async def verify_checkout(
    body: VerifyCheckoutRequest,
    actor: ActorDep,
    use_case: Annotated[VerifyCheckoutUseCase, Depends(deps.verify_checkout_uc)],
) -> PaymentResultResponse:
    """Confirm the booking from the browser's post-payment callback.

    Three checks, in order: the HMAC signature proves Razorpay issued this
    `order_id`/`payment_id` pair; fetching the payment from the gateway proves
    what it was actually worth and whether the money was *captured* rather than
    merely authorised; and the amount is compared against the booking.

    A signature alone is not enough — a client could replay a genuine ₹1 payment
    from another order it also owns.

    **This is a convenience path, not the authority.** The webhook is what
    guarantees confirmation; this exists so the guest sees a result immediately
    instead of polling. Both are idempotent, so whichever arrives first wins and
    the other is a no-op.
    """
    result = await use_case.execute(
        dto.VerifyCheckoutInput(
            razorpay_order_id=body.razorpay_order_id,
            razorpay_payment_id=body.razorpay_payment_id,
            razorpay_signature=body.razorpay_signature,
        ),
        actor,
    )
    return PaymentResultResponse(**dto_dict(result))


@router.post(
    "/retry",
    response_model=PaymentResultResponse,
    summary="Check whether a booking's payment can be retried",
)
async def retry_payment(
    body: CreateOrderRequest,
    actor: ActorDep,
    use_case: Annotated[RetryPaymentUseCase, Depends(deps.retry_payment_uc)],
) -> PaymentResultResponse:
    """Confirm the booking is still payable, then call `/orders` for a **new**
    order.

    Never reuses the previous order. Razorpay orders are not designed to be
    paid twice — a reused one produces confusing dashboard state and, on some
    methods, a duplicate charge.

    Retries only work while the booking's hold is alive. Once it lapses the
    rooms are gone and paying would produce a booking with no inventory.
    """
    result = await use_case.execute(body.booking_id, actor)
    return PaymentResultResponse(**dto_dict(result))


# ══════════════════════════════════════════════════════════════════════════
# History
# ══════════════════════════════════════════════════════════════════════════


@router.get("", response_model=PaymentListResponse, summary="Your transaction history")
async def list_payments(
    actor: ActorDep,
    use_case: Annotated[ListPaymentsUseCase, Depends(deps.list_payments_uc)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> PaymentListResponse:
    """Newest first, cursor-paged."""
    view = await use_case.execute((limit, cursor), actor)
    return PaymentListResponse(
        items=[_payment_response(v) for v in view.items], next_cursor=view.next_cursor
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    summary="Payment detail with its full ledger",
    responses={404: {"description": "No payment with that id that you may see"}},
)
async def get_payment(
    payment_id: uuid.UUID,
    actor: ActorDep,
    use_case: Annotated[GetPaymentUseCase, Depends(deps.get_payment_uc)],
) -> PaymentResponse:
    """Includes the append-only ledger: the charge, every refund, the gateway's
    fee and any chargeback.

    `net_minor` is `sum(ledger)` — what the platform actually holds — rather
    than a maintained column, so it cannot drift from the entries it is derived
    from.

    Someone else's payment is **404**, never 403.
    """
    return _payment_response(await use_case.execute(payment_id, actor))


# ══════════════════════════════════════════════════════════════════════════
# Refunds
# ══════════════════════════════════════════════════════════════════════════


@admin_router.post(
    "/{payment_id}/refund",
    response_model=PaymentResultResponse,
    dependencies=[CanRefund],
    summary="Refund a payment",
    responses={409: {"description": "Refund exceeds the amount still refundable"}},
)
async def refund_payment(
    payment_id: uuid.UUID,
    body: RefundRequest,
    actor: ActorDep,
    use_case: Annotated[IssueRefundUseCase, Depends(deps.issue_refund_uc)],
) -> PaymentResultResponse:
    """Manual refund, for support.

    Guest-initiated refunds do **not** come through here — cancelling a booking
    emits `RefundRequested` and a worker executes it, so the refund amount is
    always the one the cancellation policy computed rather than one a support
    agent typed.

    Idempotent per booking: the key is derived from the booking id, so a
    double-clicked button and a retried task both refund once.
    """
    result = await use_case.execute(
        dto.RefundInput(
            payment_id=payment_id,
            amount_minor=body.amount_minor,
            reason=body.reason,
            speed=body.speed,
        ),
        actor,
    )
    return PaymentResultResponse(**dto_dict(result))


@admin_router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    dependencies=[CanReadAny],
    summary="Any payment, for support",
)
async def admin_get_payment(
    payment_id: uuid.UUID,
    actor: ActorDep,
    use_case: Annotated[GetPaymentUseCase, Depends(deps.get_payment_uc)],
) -> PaymentResponse:
    return _payment_response(await use_case.execute(payment_id, actor))


# ══════════════════════════════════════════════════════════════════════════
# Webhook
# ══════════════════════════════════════════════════════════════════════════


@webhook_router.post(
    "/razorpay",
    response_model=WebhookAck,
    include_in_schema=False,
    summary="Razorpay webhook receiver",
)
async def razorpay_webhook(
    request: Request,
    response: Response,
    use_case: Annotated[ProcessWebhookUseCase, Depends(deps.process_webhook_uc)],
    x_razorpay_signature: Annotated[str | None, Header()] = None,
    x_razorpay_event_id: Annotated[str | None, Header()] = None,
) -> WebhookAck:
    """The authoritative payment path.

    **Reads the raw body.** `await request.body()` before any parsing — the
    HMAC is over the exact bytes Razorpay sent, and `json.dumps(await
    request.json())` produces different ones (key order, whitespace, unicode
    escaping). The signature would never match, and "fixing" that by loosening
    the check removes the protection entirely.

    **Answers 200 for duplicates and for events it does not handle.** Razorpay
    redelivers on any non-2xx; a handler that errors on normal traffic buries
    the real failures under retries.

    Exempt from rate limiting — see `_WEBHOOK` in the rate-limit middleware.
    """
    raw_body = await request.body()

    if not x_razorpay_signature:
        # No signature at all. Not an authentication failure to report in
        # detail — just refused.
        logger.warning("webhook_missing_signature", bytes=len(raw_body))
        raise ValidationError("Missing signature")

    try:
        payload: dict[str, Any] = orjson.loads(raw_body)
    except orjson.JSONDecodeError as exc:
        raise ValidationError("Malformed webhook payload") from exc

    # Razorpay always sends x-razorpay-event-id; the fallback keeps a
    # misconfigured test delivery from crashing rather than being rejected.
    event_id = x_razorpay_event_id or f"anon-{hash(raw_body)}"

    result = await use_case.execute(
        dto.WebhookInput(
            raw_body=raw_body,
            signature=x_razorpay_signature,
            event_id=event_id,
            payload=payload,
        ),
        actor=_WEBHOOK_ACTOR,
    )
    response.status_code = status.HTTP_200_OK
    return WebhookAck(status=str(result.get("status", "ok")))


# ══════════════════════════════════════════════════════════════════════════


def _payment_response(view: dto.PaymentView) -> PaymentResponse:
    return PaymentResponse(
        **(
            dto_dict(view)
            | {
                "refunds": [dto_dict(r) for r in view.refunds],
                "ledger": [dto_dict(e) for e in view.ledger],
            }
        )
    )
