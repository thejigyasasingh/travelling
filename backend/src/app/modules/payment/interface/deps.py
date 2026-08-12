"""Payment module wiring.

Two things here are worth reading twice.

**The gateway is a singleton from the container, not built per request.** It
owns an HTTP connection pool and a circuit breaker; rebuilding it per request
throws away the pool and resets the breaker on every call, which is the same as
not having one.

**The booking service is constructed from *this* module's session.** So the
payment row, the ledger entries and the booking confirmation they cause all
commit together or not at all. Splitting them across two transactions produces
the worst possible failure: money taken, booking unconfirmed.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from app.interface.api.deps import ContainerDep
from app.modules.payment.application.ports import PaymentGateway
from app.modules.payment.application.use_cases.checkout import (
    CreateOrderUseCase,
    VerifyCheckoutUseCase,
)
from app.modules.payment.application.use_cases.history import (
    GetPaymentUseCase,
    ListPaymentsUseCase,
)
from app.modules.payment.application.use_cases.refunds import (
    CaptureAuthorizedUseCase,
    IssueRefundUseCase,
    ReconcilePaymentsUseCase,
    RetryPaymentUseCase,
)
from app.modules.payment.application.use_cases.webhooks import ProcessWebhookUseCase
from app.modules.payment.domain.errors import PaymentsDisabledError
from app.modules.payment.infrastructure.unit_of_work import PaymentUow


async def get_payment_uow(container: ContainerDep) -> AsyncIterator[PaymentUow]:
    """Always the **primary**. Never a replica.

    A payment read from a replica is stale by the length of replication lag,
    and "is this already captured?" answered from stale data is a double
    charge.
    """
    async with container.database.write_session() as session:
        uow = PaymentUow(session)
        yield uow
        await uow.flush()


PaymentUowDep = Annotated[PaymentUow, Depends(get_payment_uow)]


def get_gateway(container: ContainerDep) -> PaymentGateway:
    """The configured gateway, or a clean 503.

    Payments off means no credentials, and the alternative to failing here is
    an ``AttributeError`` in the middle of a checkout. 503 is honest: the
    capability exists, this deployment is not configured for it.
    """
    if container.payment_gateway is None:
        raise PaymentsDisabledError
    return container.payment_gateway


GatewayDep = Annotated[PaymentGateway, Depends(get_gateway)]


# ══════════════════════════════════════════════════════════════════════════
# Use-case providers
# ══════════════════════════════════════════════════════════════════════════


def create_order_uc(
    container: ContainerDep, uow: PaymentUowDep, gateway: GatewayDep
) -> CreateOrderUseCase:
    return CreateOrderUseCase(
        payments=uow.payments,
        bookings=uow.bookings,
        gateway=gateway,
        clock=container.clock,
    )


def verify_checkout_uc(
    container: ContainerDep, uow: PaymentUowDep, gateway: GatewayDep
) -> VerifyCheckoutUseCase:
    return VerifyCheckoutUseCase(
        payments=uow.payments,
        bookings=uow.bookings,
        gateway=gateway,
        clock=container.clock,
    )


def retry_payment_uc(
    container: ContainerDep, uow: PaymentUowDep, gateway: GatewayDep
) -> RetryPaymentUseCase:
    return RetryPaymentUseCase(
        payments=uow.payments,
        bookings=uow.bookings,
        gateway=gateway,
        clock=container.clock,
    )


def issue_refund_uc(
    container: ContainerDep, uow: PaymentUowDep, gateway: GatewayDep
) -> IssueRefundUseCase:
    return IssueRefundUseCase(
        payments=uow.payments,
        bookings=uow.bookings,
        gateway=gateway,
        clock=container.clock,
    )


def process_webhook_uc(
    container: ContainerDep, uow: PaymentUowDep, gateway: GatewayDep
) -> ProcessWebhookUseCase:
    return ProcessWebhookUseCase(
        payments=uow.payments,
        bookings=uow.bookings,
        events=uow.events,
        gateway=gateway,
        clock=container.clock,
    )


def capture_authorized_uc(
    container: ContainerDep, uow: PaymentUowDep, gateway: GatewayDep
) -> CaptureAuthorizedUseCase:
    return CaptureAuthorizedUseCase(
        payments=uow.payments,
        bookings=uow.bookings,
        gateway=gateway,
        clock=container.clock,
    )


def reconcile_payments_uc(
    container: ContainerDep, uow: PaymentUowDep, gateway: GatewayDep
) -> ReconcilePaymentsUseCase:
    return ReconcilePaymentsUseCase(
        payments=uow.payments,
        bookings=uow.bookings,
        gateway=gateway,
        clock=container.clock,
    )


# Reads need no gateway — a history page must render when Razorpay is down.
def get_payment_uc(container: ContainerDep, uow: PaymentUowDep) -> GetPaymentUseCase:
    return GetPaymentUseCase(payments=uow.payments, clock=container.clock)


def list_payments_uc(container: ContainerDep, uow: PaymentUowDep) -> ListPaymentsUseCase:
    return ListPaymentsUseCase(payments=uow.payments, clock=container.clock)
