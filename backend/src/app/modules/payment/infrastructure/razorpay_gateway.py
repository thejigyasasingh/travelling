"""Razorpay HTTP adapter.

Written against the REST API rather than the official SDK, deliberately:

* The SDK is **synchronous**. Calling it from an async handler blocks the event
  loop for the length of a payment-gateway round trip — 200-800 ms — and a
  handful of concurrent checkouts stalls every other request on the worker.
* It has no typing, so a shape change surfaces as an ``AttributeError`` in
  production rather than at review.
* It has no circuit breaker. A degraded Razorpay would otherwise hold every
  worker in the pool until it timed out. Here the shared
  :class:`HttpClient` opens a circuit and fails fast instead.

**Amounts are integer paise, everywhere.** Razorpay's API is minor units and so
is ours, so no conversion happens at this boundary — which is the point, since
a float conversion in a payments adapter is how a ₹1,499.50 charge becomes
₹1,499.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Final

import httpx

from app.core.logging import get_logger
from app.core.types.money import Money
from app.infrastructure.external.http_client import HttpClient
from app.infrastructure.external.resilience.circuit_breaker import CircuitBreakerConfig
from app.modules.payment.application.ports import (
    GatewayOrder,
    GatewayPayment,
    GatewayRefund,
)
from app.modules.payment.domain import errors
from app.modules.payment.domain.signature import (
    SignatureError,
    verify_checkout,
    verify_webhook,
)
from app.modules.payment.domain.value_objects import (
    MAX_ORDER_AMOUNT_MINOR,
    PaymentMethod,
    RefundSpeed,
)

logger = get_logger(__name__)

RAZORPAY_BASE_URL: Final = "https://api.razorpay.com/v1"

#: Razorpay error codes that mean "the bank said no". Retrying the same
#: instrument will fail again, so the guest needs a different method — a retry
#: button here is worse than useless.
_DECLINE_CODES: Final = frozenset({"BAD_REQUEST_ERROR", "GATEWAY_ERROR"})

#: Payment operations are not idempotent by default, so the circuit is
#: deliberately conservative: better to fail fast and let the guest retry than
#: to hammer a struggling gateway with charge attempts.
_BREAKER: Final = CircuitBreakerConfig(
    failure_threshold=5,
    success_threshold=2,
    reset_timeout_seconds=30.0,
    half_open_max_calls=2,
)


@dataclass(slots=True)
class RazorpayConfig:
    key_id: str
    key_secret: str
    webhook_secret: str
    #: Auto-capture means Razorpay takes the money the moment it is authorised.
    #: On by default: a separate capture step is another chance to fail, and an
    #: uncaptured authorisation silently reverses after a few days, leaving a
    #: confirmed booking nobody was paid for.
    auto_capture: bool = True
    base_url: str = RAZORPAY_BASE_URL


class RazorpayGateway:
    """Implements :class:`app.modules.payment.application.ports.PaymentGateway`."""

    def __init__(self, config: RazorpayConfig) -> None:
        self._config = config
        credentials = base64.b64encode(f"{config.key_id}:{config.key_secret}".encode()).decode()
        self._http = HttpClient(
            name="razorpay",
            base_url=config.base_url,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            # A payment gateway legitimately takes a few seconds to think about
            # a capture; connect failures should still surface immediately.
            timeout=httpx.Timeout(connect=3.0, read=15.0, write=10.0, pool=2.0),
            max_connections=20,
            breaker_config=_BREAKER,
        )

    @property
    def public_key(self) -> str:
        """The key id, which the browser needs to open checkout. Public by
        design — it identifies the merchant, it does not authorise anything."""
        return self._config.key_id

    # ── orders ────────────────────────────────────────────────────────────

    async def create_order(
        self,
        *,
        amount: Money,
        receipt: str,
        notes: dict[str, str],
        auto_capture: bool | None = None,
    ) -> GatewayOrder:
        """Create the order the client's checkout will reference.

        ``receipt`` carries our booking reference, so a payment can be matched
        to a booking from the Razorpay dashboard during an incident without
        touching our database at all.
        """
        if amount.amount_minor > MAX_ORDER_AMOUNT_MINOR:
            raise errors.GatewayError(
                "This amount exceeds the payment limit. Please contact support.",
                gateway_code="AMOUNT_LIMIT",
            )

        capture = self._config.auto_capture if auto_capture is None else auto_capture
        body = {
            "amount": amount.amount_minor,  # paise; no conversion, by design
            "currency": amount.currency,
            "receipt": receipt[:40],
            "notes": notes,
            # 1 = capture automatically on authorisation.
            "payment_capture": 1 if capture else 0,
        }
        data = await self._post("/orders", body, operation="create_order")

        return GatewayOrder(
            id=str(data["id"]),
            amount=Money(int(data["amount"]), str(data["currency"])),
            receipt=str(data.get("receipt", "")),
            status=str(data.get("status", "created")),
        )

    # ── payments ──────────────────────────────────────────────────────────

    async def fetch_payment(self, payment_id: str) -> GatewayPayment:
        """Ask the gateway what actually happened.

        The authority for every verification. A client's callback says a
        payment succeeded; this says whether it did, for how much, and whether
        the money was captured or merely authorised.
        """
        data = await self._get(f"/payments/{payment_id}", operation="fetch_payment")
        return self._to_payment(data)

    async def capture(self, payment_id: str, amount: Money) -> GatewayPayment:
        """Take authorised funds. Only used when auto-capture is off."""
        data = await self._post(
            f"/payments/{payment_id}/capture",
            {"amount": amount.amount_minor, "currency": amount.currency},
            operation="capture",
        )
        return self._to_payment(data)

    # ── refunds ───────────────────────────────────────────────────────────

    async def refund(
        self,
        *,
        payment_id: str,
        amount: Money,
        idempotency_key: str,
        notes: dict[str, str] | None = None,
        speed: RefundSpeed = RefundSpeed.NORMAL,
    ) -> GatewayRefund:
        """Return money to the guest.

        ``X-Razorpay-Idempotency-Key`` is what makes this safe to retry. Our own
        in-process guard covers one worker; this covers every worker, every
        redelivery, and the support agent clicking twice.
        """
        data = await self._post(
            f"/payments/{payment_id}/refund",
            {
                "amount": amount.amount_minor,
                "speed": speed.value,
                "notes": notes or {},
            },
            operation="refund",
            extra_headers={"X-Razorpay-Idempotency-Key": idempotency_key},
        )
        return GatewayRefund(
            id=str(data["id"]),
            payment_id=str(data.get("payment_id", payment_id)),
            amount=Money(int(data["amount"]), str(data.get("currency", amount.currency))),
            status=str(data.get("status", "pending")),
            speed=str(data.get("speed_processed", speed.value)),
            raw=data,
        )

    # ── signatures ────────────────────────────────────────────────────────

    def verify_checkout_signature(self, *, order_id: str, payment_id: str, signature: str) -> None:
        """Signed with **KEY_SECRET** over ``order_id|payment_id``."""
        try:
            verify_checkout(
                order_id=order_id,
                payment_id=payment_id,
                signature=signature,
                key_secret=self._config.key_secret,
            )
        except SignatureError as exc:
            logger.warning("checkout_signature_invalid", order_id=order_id, payment_id=payment_id)
            raise errors.SignatureVerificationError("checkout") from exc

    def verify_webhook_signature(self, *, raw_body: bytes, signature: str) -> None:
        """Signed with **WEBHOOK_SECRET** over the raw request body.

        A different secret from the API key on purpose: a leaked webhook secret
        must not let anyone call the API, and vice versa.
        """
        try:
            verify_webhook(
                raw_body=raw_body,
                signature=signature,
                webhook_secret=self._config.webhook_secret,
            )
        except SignatureError as exc:
            logger.warning("webhook_signature_invalid", body_bytes=len(raw_body))
            raise errors.SignatureVerificationError("webhook") from exc

    # ── transport ─────────────────────────────────────────────────────────

    async def _post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        operation: str,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._http.post(path, json=body, headers=extra_headers or {})
        except Exception as exc:
            logger.error("razorpay_unreachable", operation=operation, error=str(exc))
            raise errors.GatewayError from exc
        return self._parse(response, operation=operation)

    async def _get(self, path: str, *, operation: str) -> dict[str, Any]:
        try:
            response = await self._http.get(path)
        except Exception as exc:
            logger.error("razorpay_unreachable", operation=operation, error=str(exc))
            raise errors.GatewayError from exc
        return self._parse(response, operation=operation)

    @staticmethod
    def _parse(response: httpx.Response, *, operation: str) -> dict[str, Any]:
        """Turn Razorpay's response into data or the right kind of error.

        The distinction between :class:`PaymentDeclinedError` and
        :class:`GatewayError` matters to the guest: a decline needs a different
        card, an outage needs the same one again in a minute. Collapsing them
        into "payment failed" sends everyone to support.
        """
        if response.status_code < 300:
            payload: dict[str, Any] = response.json()
            return payload

        try:
            error = response.json().get("error", {})
        except ValueError:  # pragma: no cover — Razorpay always returns JSON
            error = {}

        code = str(error.get("code", "")) or None
        description = str(error.get("description", "")) or None

        logger.warning(
            "razorpay_error",
            operation=operation,
            status=response.status_code,
            code=code,
            description=description,
        )

        if response.status_code == 400 and code in _DECLINE_CODES:
            raise errors.PaymentDeclinedError(description, gateway_code=code)
        raise errors.GatewayError(gateway_code=code)

    @staticmethod
    def _to_payment(data: dict[str, Any]) -> GatewayPayment:
        currency = str(data.get("currency", "INR"))
        method = PaymentMethod.parse(data.get("method"))

        # Razorpay reports the card's last 4 or the UPI VPA depending on the
        # method. Stored so a guest asking "which card was this?" can be
        # answered without a dashboard login.
        identifier = None
        if method is PaymentMethod.UPI:
            identifier = data.get("vpa")
        elif method is PaymentMethod.CARD:
            card = data.get("card") or {}
            identifier = card.get("last4")

        return GatewayPayment(
            id=str(data["id"]),
            order_id=str(data["order_id"]) if data.get("order_id") else None,
            amount=Money(int(data["amount"]), currency),
            status=str(data.get("status", "created")),
            method=method,
            captured=bool(data.get("captured", False)),
            # Present only after capture.
            fee=Money(int(data["fee"]), currency) if data.get("fee") else None,
            tax=Money(int(data["tax"]), currency) if data.get("tax") else None,
            vpa_or_last4=str(identifier) if identifier else None,
            error_code=str(data["error_code"]) if data.get("error_code") else None,
            error_description=(
                str(data["error_description"]) if data.get("error_description") else None
            ),
            raw=data,
        )

    async def aclose(self) -> None:
        await self._http.aclose()
