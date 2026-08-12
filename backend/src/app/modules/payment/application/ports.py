"""Ports for the payment module."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from app.core.types.money import Money
from app.modules.payment.domain.entities import Payment
from app.modules.payment.domain.value_objects import PaymentMethod, RefundSpeed


@dataclass(frozen=True, slots=True)
class GatewayOrder:
    id: str
    amount: Money
    receipt: str
    status: str


@dataclass(frozen=True, slots=True)
class GatewayPayment:
    """A payment as the gateway sees it.

    ``amount`` is what the gateway says was charged, and is always
    cross-checked against our own expected amount — never trusted on its own.
    """

    id: str
    order_id: str | None
    amount: Money
    status: str
    method: PaymentMethod
    captured: bool
    #: Razorpay's fee and the tax on it, in minor units. Present only after
    #: capture. Recorded as ledger entries so reconciliation against the
    #: settlement report can balance.
    fee: Money | None = None
    tax: Money | None = None
    vpa_or_last4: str | None = None
    error_code: str | None = None
    error_description: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GatewayRefund:
    id: str
    payment_id: str
    amount: Money
    status: str
    speed: str
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentGateway(Protocol):
    """Everything the module needs from Razorpay.

    A protocol rather than the SDK directly: the SDK is synchronous, untyped,
    and would put a blocking HTTP call inside an async request handler. It also
    keeps a second gateway for a new market from being a change to the use
    cases.
    """

    async def create_order(
        self,
        *,
        amount: Money,
        receipt: str,
        notes: dict[str, str],
        auto_capture: bool = True,
    ) -> GatewayOrder: ...

    async def fetch_payment(self, payment_id: str) -> GatewayPayment:
        """Authoritative state, straight from the gateway.

        Used to verify a client callback and to reconcile a payment whose
        webhook never arrived. The gateway is the source of truth; our row is a
        cache of it.
        """
        ...

    async def capture(self, payment_id: str, amount: Money) -> GatewayPayment:
        """Take previously authorised funds.

        Only needed when auto-capture is off. An uncaptured authorisation
        reverses after a few days, so this has a deadline.
        """
        ...

    async def refund(
        self,
        *,
        payment_id: str,
        amount: Money,
        idempotency_key: str,
        notes: dict[str, str] | None = None,
        speed: RefundSpeed = RefundSpeed.NORMAL,
    ) -> GatewayRefund:
        """Return money.

        ``idempotency_key`` goes to Razorpay as a header. It is the only thing
        that stops a retried task from refunding twice — our own guard covers
        one process, this covers all of them.
        """
        ...

    def verify_checkout_signature(self, *, order_id: str, payment_id: str, signature: str) -> None:
        """Raise unless the browser's callback is genuine."""
        ...

    def verify_webhook_signature(self, *, raw_body: bytes, signature: str) -> None:
        """Raise unless the webhook is genuine. ``raw_body`` must be the exact
        bytes received — see ``domain/signature.py``."""
        ...

    @property
    def public_key(self) -> str:
        """The key id the client needs to open checkout. Public by design."""
        ...


class PaymentRepository(Protocol):
    async def get(self, payment_id: uuid.UUID) -> Payment | None: ...

    async def get_by_order_id(self, order_id: str) -> Payment | None:
        """Webhooks and callbacks identify a payment by its *order*."""
        ...

    async def get_by_gateway_payment_id(self, gateway_payment_id: str) -> Payment | None: ...

    async def get_active_for_booking(self, booking_id: uuid.UUID) -> Payment | None:
        """The attempt currently in play, if any.

        Stops a guest opening checkout twice in two tabs and producing two
        live orders for one booking.
        """
        ...

    async def add(self, payment: Payment) -> None: ...

    async def count_attempts(self, booking_id: uuid.UUID) -> int: ...

    async def list_for_guest(
        self,
        guest_id: uuid.UUID,
        *,
        limit: int = 20,
        cursor: tuple[datetime, uuid.UUID] | None = None,
    ) -> tuple[list[Payment], bool]: ...

    async def find_stale_authorized(
        self, *, older_than: datetime, limit: int = 100
    ) -> list[Payment]:
        """Authorisations that must be captured before they reverse."""
        ...

    async def find_pending_reconciliation(
        self, *, older_than: datetime, limit: int = 100
    ) -> list[Payment]:
        """Payments stuck in a non-terminal state whose webhook never arrived.

        Webhooks are delivered "at least once", which in practice sometimes
        means "eventually" and occasionally "never". Polling the gateway for
        these is the safety net.
        """
        ...


class WebhookEventStore(Protocol):
    """Deduplicates webhook deliveries.

    Razorpay redelivers on any non-2xx response, and duplicates arrive even on
    success. Without this, one ``payment.captured`` redelivered three times
    would attempt three confirmations.
    """

    async def claim(
        self, *, event_id: str, event_type: str, payload: dict[str, Any], now: datetime
    ) -> bool:
        """Atomically record the event. ``False`` means already seen."""
        ...

    async def mark_processed(self, event_id: str, *, now: datetime) -> None: ...

    async def mark_failed(self, event_id: str, *, error: str, now: datetime) -> None: ...

    async def find_unprocessed(self, *, limit: int = 100) -> Sequence[dict[str, Any]]: ...
