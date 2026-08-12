"""Reading payments: detail and transaction history."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.core.clock import Clock
from app.core.logging import get_logger
from app.core.types.pagination import Cursor
from app.modules.payment.application.dto import (
    LedgerEntryView,
    PaymentListView,
    PaymentView,
    RefundView,
)
from app.modules.payment.application.ports import PaymentRepository
from app.modules.payment.domain.entities import Payment
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)


def to_payment_view(payment: Payment) -> PaymentView:
    """Map for the wire.

    The ledger is included in full. It is the only place a guest — or a support
    agent — can see why the amount they were charged, the amount refunded and
    the amount the platform kept are three different numbers.
    """
    return PaymentView(
        id=payment.id,
        status=payment.status.value,
        booking_id=payment.booking_id,
        booking_reference=payment.booking_reference,
        amount_minor=payment.expected_amount.amount_minor,
        currency=payment.currency,
        method=payment.method.value,
        instrument=payment.vpa_or_last4,
        gateway_order_id=payment.gateway_order_id,
        gateway_payment_id=payment.gateway_payment_id,
        attempt_number=payment.attempt_number,
        created_at=payment.created_at,
        authorized_at=payment.authorized_at,
        captured_at=payment.captured_at,
        failure_code=payment.failure_code,
        failure_reason=payment.failure_reason,
        refunded_minor=payment.refunded_amount.amount_minor,
        refundable_minor=payment.refundable_amount.amount_minor,
        # Derived from the entries, never a stored column — so it cannot drift
        # from what it claims to summarise.
        net_minor=payment.net_position.amount_minor,
        refunds=[
            RefundView(
                id=r.id,
                status=r.status.value,
                amount_minor=r.amount.amount_minor,
                currency=r.amount.currency,
                reason=r.reason,
                speed=r.speed.value,
                gateway_refund_id=r.gateway_refund_id,
                requested_at=r.requested_at,
                completed_at=r.completed_at,
                failure_reason=r.failure_reason,
            )
            for r in payment.refunds
        ],
        ledger=[
            LedgerEntryView(
                kind=e.kind.value,
                amount_minor=e.amount.amount_minor,
                currency=e.amount.currency,
                signed_minor=e.signed_amount.amount_minor,
                occurred_at=e.occurred_at,
                gateway_reference=e.gateway_reference,
                note=e.note,
            )
            for e in payment.ledger
        ],
    )


@dataclass(slots=True)
class GetPaymentUseCase:
    payments: PaymentRepository
    clock: Clock

    async def execute(self, payment_id: uuid.UUID, actor: Actor) -> PaymentView:
        payment = await self.payments.get(payment_id)
        if payment is None:
            raise EntityNotFoundError("Payment", payment_id)
        # Raises PaymentAccessDeniedError, which the interface maps to 404 — a
        # 403 would confirm the id exists and let someone enumerate payments.
        payment.assert_visible_to(
            user_id=actor.user_id, is_staff=actor.has_role("admin", "superadmin", "support")
        )
        return to_payment_view(payment)


@dataclass(slots=True)
class ListPaymentsUseCase:
    """The guest's transaction history. Cursor-paged."""

    payments: PaymentRepository
    clock: Clock

    async def execute(self, args: tuple[int, str | None], actor: Actor) -> PaymentListView:
        limit, raw_cursor = args
        if actor.user_id is None:  # pragma: no cover — route requires auth
            return PaymentListView(items=[])

        cursor = None
        if raw_cursor:
            values = Cursor.decode(raw_cursor).values
            cursor = (datetime.fromisoformat(str(values[0])), uuid.UUID(str(values[1])))

        items, has_more = await self.payments.list_for_guest(
            actor.user_id, limit=limit, cursor=cursor
        )
        views = [to_payment_view(p) for p in items]

        next_cursor = None
        if has_more and items:
            last = items[-1]
            # Mirrors the ORDER BY exactly — (created_at, id). The id is the
            # tiebreaker: without it, payments created in the same millisecond
            # are skipped or repeated across pages.
            next_cursor = Cursor((last.created_at, str(last.id))).encode()

        return PaymentListView(items=views, next_cursor=next_cursor)
