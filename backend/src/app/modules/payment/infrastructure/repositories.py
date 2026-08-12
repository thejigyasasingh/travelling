"""Payment persistence and the webhook dedupe store."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, Result, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.core.logging import get_logger
from app.core.types.money import Money
from app.modules.payment.domain.entities import LedgerEntry, Payment, RefundAttempt
from app.modules.payment.domain.value_objects import (
    PaymentMethod,
    PaymentStatus,
    RefundSpeed,
    RefundStatus,
    TransactionKind,
)
from app.modules.payment.infrastructure.models import (
    LedgerEntryModel,
    PaymentModel,
    PaymentRefundModel,
    WebhookEventModel,
)

logger = get_logger(__name__)


def _affected(result: Result[Any]) -> int:
    """``execute()`` is typed as returning ``Result``, which has no
    ``rowcount``; a DML statement actually yields a ``CursorResult`` that does.
    The cast keeps one narrow lie in one place instead of an ``ignore`` at every
    call site."""
    return int(cast("CursorResult[Any]", result).rowcount or 0)


def _money(minor: int | None, currency: str) -> Money | None:
    return Money(minor, currency) if minor is not None else None


def _to_domain(row: PaymentModel) -> Payment:
    currency = row.currency
    return Payment(
        entity_id=row.id,
        booking_id=row.booking_id,
        booking_reference=row.booking_reference,
        guest_id=row.guest_id,
        expected_amount=Money(row.expected_amount_minor, currency),
        gateway_order_id=row.gateway_order_id,
        gateway=row.gateway,
        status=PaymentStatus(row.status),
        gateway_payment_id=row.gateway_payment_id,
        method=PaymentMethod(row.method),
        vpa_or_last4=row.instrument,
        attempt_number=row.attempt_number,
        authorized_at=row.authorized_at,
        captured_at=row.captured_at,
        failure_code=row.failure_code,
        failure_reason=row.failure_reason,
        gateway_fee=_money(row.gateway_fee_minor, currency),
        gateway_tax=_money(row.gateway_tax_minor, currency),
        refunds=[
            RefundAttempt(
                entity_id=r.id,
                amount=Money(r.amount_minor, r.currency),
                reason=r.reason,
                idempotency_key=r.idempotency_key,
                requested_at=r.requested_at,
                booking_id=r.booking_id,
                speed=RefundSpeed(r.speed),
                status=RefundStatus(r.status),
                gateway_refund_id=r.gateway_refund_id,
                failure_reason=r.failure_reason,
                completed_at=r.completed_at,
            )
            for r in row.refunds
        ],
        ledger=[
            LedgerEntry(
                entity_id=e.id,
                kind=TransactionKind(e.kind),
                amount=Money(e.amount_minor, e.currency),
                occurred_at=e.occurred_at,
                gateway_reference=e.gateway_reference,
                note=e.note,
            )
            for e in row.ledger
        ],
        notes=dict(row.notes or {}),
        created_at=row.created_at,
        version=row.version,
    )


def _to_model(payment: Payment) -> PaymentModel:
    row = PaymentModel(
        id=payment.id,
        booking_id=payment.booking_id,
        booking_reference=payment.booking_reference,
        guest_id=payment.guest_id,
        gateway=payment.gateway,
        gateway_order_id=payment.gateway_order_id,
        gateway_payment_id=payment.gateway_payment_id,
        status=payment.status.value,
        method=payment.method.value,
        instrument=payment.vpa_or_last4,
        expected_amount_minor=payment.expected_amount.amount_minor,
        currency=payment.currency,
        attempt_number=payment.attempt_number,
        notes=payment.notes,
    )
    return row


def _apply(payment: Payment, row: PaymentModel) -> None:
    """Write mutable state back.

    ``expected_amount_minor`` is deliberately absent: what a payment is *for* is
    fixed when the order is created. A repriced booking gets a new payment, and
    silently updating the amount here would break every reconciliation that had
    already counted the original.
    """
    row.status = payment.status.value
    row.gateway_payment_id = payment.gateway_payment_id
    row.method = payment.method.value
    row.instrument = payment.vpa_or_last4
    row.authorized_at = payment.authorized_at
    row.captured_at = payment.captured_at
    row.failure_code = payment.failure_code
    row.failure_reason = payment.failure_reason
    row.gateway_fee_minor = payment.gateway_fee.amount_minor if payment.gateway_fee else None
    row.gateway_tax_minor = payment.gateway_tax.amount_minor if payment.gateway_tax else None

    existing_refunds = {r.id: r for r in row.refunds}
    for attempt in payment.refunds:
        if (current := existing_refunds.get(attempt.id)) is None:
            row.refunds.append(
                PaymentRefundModel(
                    id=attempt.id,
                    payment_id=payment.id,
                    booking_id=attempt.booking_id,
                    status=attempt.status.value,
                    amount_minor=attempt.amount.amount_minor,
                    currency=attempt.amount.currency,
                    reason=attempt.reason,
                    speed=attempt.speed.value,
                    idempotency_key=attempt.idempotency_key,
                    gateway_refund_id=attempt.gateway_refund_id,
                    failure_reason=attempt.failure_reason,
                    requested_at=attempt.requested_at,
                    completed_at=attempt.completed_at,
                )
            )
        else:
            current.status = attempt.status.value
            current.gateway_refund_id = attempt.gateway_refund_id
            current.failure_reason = attempt.failure_reason
            current.completed_at = attempt.completed_at

    # Ledger entries are append-only: new ones are added, existing ones are
    # never touched. That immutability is the whole value of the ledger.
    known = {e.id for e in row.ledger}
    for entry in payment.ledger:
        if entry.id in known:
            continue
        row.ledger.append(
            LedgerEntryModel(
                id=entry.id,
                payment_id=payment.id,
                booking_id=payment.booking_id,
                kind=entry.kind.value,
                amount_minor=entry.amount.amount_minor,
                signed_minor=entry.signed_amount.amount_minor,
                currency=entry.amount.currency,
                occurred_at=entry.occurred_at,
                gateway_reference=entry.gateway_reference,
                note=entry.note,
            )
        )


class SqlPaymentRepository:
    """Implements
    :class:`app.modules.payment.application.ports.PaymentRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._identity: dict[uuid.UUID, tuple[Payment, PaymentModel]] = {}

    async def get(self, payment_id: uuid.UUID) -> Payment | None:
        if payment_id in self._identity:
            return self._identity[payment_id][0]
        return self._track(await self._session.get(PaymentModel, payment_id))

    async def get_by_order_id(self, order_id: str) -> Payment | None:
        row = (
            await self._session.execute(
                select(PaymentModel).where(PaymentModel.gateway_order_id == order_id)
            )
        ).scalar_one_or_none()
        return self._track(row)

    async def get_by_gateway_payment_id(self, gateway_payment_id: str) -> Payment | None:
        row = (
            await self._session.execute(
                select(PaymentModel).where(PaymentModel.gateway_payment_id == gateway_payment_id)
            )
        ).scalar_one_or_none()
        return self._track(row)

    async def get_active_for_booking(self, booking_id: uuid.UUID) -> Payment | None:
        """The attempt currently in play.

        Ordered by attempt so a retry supersedes its predecessor, and filtered
        to non-terminal states plus captured — a captured payment is very much
        "active" for the purpose of refusing a second checkout.
        """
        row = (
            await self._session.execute(
                select(PaymentModel)
                .where(
                    PaymentModel.booking_id == booking_id,
                    PaymentModel.status.in_(["created", "pending", "authorized", "captured"]),
                )
                .order_by(PaymentModel.attempt_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return self._track(row)

    async def count_attempts(self, booking_id: uuid.UUID) -> int:
        return int(
            (
                await self._session.execute(
                    text("SELECT count(*) FROM payments WHERE booking_id = :b"),
                    {"b": booking_id},
                )
            ).scalar()
            or 0
        )

    async def add(self, payment: Payment) -> None:
        row = _to_model(payment)
        self._session.add(row)
        self._identity[payment.id] = (payment, row)

    async def list_for_guest(
        self,
        guest_id: uuid.UUID,
        *,
        limit: int = 20,
        cursor: tuple[datetime, uuid.UUID] | None = None,
    ) -> tuple[list[Payment], bool]:
        stmt = select(PaymentModel).where(PaymentModel.guest_id == guest_id)
        if cursor is not None:
            created_at, row_id = cursor
            stmt = stmt.where(
                text("(payments.created_at, payments.id) < (:c_at, :c_id)").bindparams(
                    c_at=created_at, c_id=row_id
                )
            )
        stmt = stmt.order_by(PaymentModel.created_at.desc(), PaymentModel.id.desc()).limit(
            limit + 1
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows[:limit]], len(rows) > limit

    async def find_stale_authorized(
        self, *, older_than: datetime, limit: int = 100
    ) -> list[Payment]:
        stmt = (
            select(PaymentModel)
            .where(
                PaymentModel.status == "authorized",
                PaymentModel.authorized_at.isnot(None),
                PaymentModel.authorized_at <= older_than,
            )
            .order_by(PaymentModel.authorized_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [p for p in (self._track(r) for r in rows) if p is not None]

    async def find_pending_reconciliation(
        self, *, older_than: datetime, limit: int = 100
    ) -> list[Payment]:
        stmt = (
            select(PaymentModel)
            .where(
                PaymentModel.status.in_(["created", "pending", "authorized"]),
                PaymentModel.created_at <= older_than,
            )
            .order_by(PaymentModel.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [p for p in (self._track(r) for r in rows) if p is not None]

    async def flush(self) -> None:
        for payment, row in self._identity.values():
            _apply(payment, row)
        await self._session.flush()

    def pending_events(self) -> list[Any]:
        events: list[Any] = []
        for payment, _ in self._identity.values():
            events.extend(payment.pull_events())
        return events

    def _track(self, row: PaymentModel | None) -> Payment | None:
        if row is None:
            return None
        if row.id in self._identity:
            return self._identity[row.id][0]
        payment = _to_domain(row)
        self._identity[row.id] = (payment, row)
        return payment


class SqlWebhookEventStore:
    """Implements
    :class:`app.modules.payment.application.ports.WebhookEventStore`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim(
        self, *, event_id: str, event_type: str, payload: dict[str, Any], now: datetime
    ) -> bool:
        """Atomic claim via ``INSERT … ON CONFLICT DO NOTHING``.

        The primary key does the work: whichever delivery inserts first wins,
        and the loser sees zero rows affected. A SELECT-then-INSERT would let
        two workers receiving the same redelivery both proceed and confirm the
        same booking twice.
        """
        stmt = (
            pg_insert(WebhookEventModel)
            .values(
                event_id=event_id,
                event_type=event_type,
                payload=payload,
                received_at=now,
                attempts=1,
            )
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        result = await self._session.execute(stmt)
        return _affected(result) > 0

    async def mark_processed(self, event_id: str, *, now: datetime) -> None:
        row = await self._session.get(WebhookEventModel, event_id)
        if row is not None:
            row.processed_at = now
            row.error = None

    async def mark_failed(self, event_id: str, *, error: str, now: datetime) -> None:
        row = await self._session.get(WebhookEventModel, event_id)
        if row is not None:
            row.error = error[:1000]
            row.attempts += 1

    async def find_unprocessed(self, *, limit: int = 100) -> Sequence[dict[str, Any]]:
        rows = (
            (
                await self._session.execute(
                    select(WebhookEventModel)
                    .where(WebhookEventModel.processed_at.is_(None))
                    .order_by(WebhookEventModel.received_at)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [
            {
                "event_id": r.event_id,
                "event_type": r.event_type,
                "payload": r.payload,
                "attempts": r.attempts,
                "error": r.error,
            }
            for r in rows
        ]

    async def purge_processed(self, *, before: datetime) -> int:
        """Retention. The raw payloads are kept long enough to replay a
        mishandled delivery and no longer — they contain the guest's name and
        contact details."""
        result = await self._session.execute(
            text("DELETE FROM payment_webhook_events WHERE processed_at < :before"),
            {"before": before},
        )
        return _affected(result)


def now() -> datetime:  # pragma: no cover — re-exported for the tasks module
    return utcnow()
