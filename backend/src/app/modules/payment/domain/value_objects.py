"""Payment value objects."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

#: Razorpay identifiers are prefixed and opaque. Validated on the way in
#: because they arrive from clients and webhooks, and an unvalidated id ends up
#: in a URL path we then call.
_ORDER_RE: Final = re.compile(r"^order_[A-Za-z0-9]{10,20}$")
_PAYMENT_RE: Final = re.compile(r"^pay_[A-Za-z0-9]{10,20}$")
_REFUND_RE: Final = re.compile(r"^rfnd_[A-Za-z0-9]{10,20}$")


class PaymentStatus(StrEnum):
    """Mirrors Razorpay's lifecycle, with our own terminal states.

    ``AUTHORIZED`` and ``CAPTURED`` are genuinely different and conflating them
    is how money goes missing: an authorised payment has the funds *reserved on
    the card* but not taken. If it is never captured it silently reverses after
    a few days, and the guest ends up with a confirmed booking nobody was paid
    for.
    """

    CREATED = "created"
    #: Async methods — UPI collect, netbanking — sit here while the customer
    #: completes the flow in their bank's app. Minutes, occasionally hours.
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    #: The customer disputed the charge with their bank. Not a refund: the
    #: money is pulled back by the network and a fee is charged on top.
    DISPUTED = "disputed"

    @property
    def is_terminal(self) -> bool:
        return self in (
            PaymentStatus.FAILED,
            PaymentStatus.REFUNDED,
            PaymentStatus.DISPUTED,
        )

    @property
    def is_money_taken(self) -> bool:
        """True when funds have actually moved.

        The single source of truth for "may this booking be confirmed?" —
        `AUTHORIZED` deliberately does not qualify.
        """
        return self in (
            PaymentStatus.CAPTURED,
            PaymentStatus.PARTIALLY_REFUNDED,
            PaymentStatus.REFUNDED,
        )

    @property
    def is_retryable(self) -> bool:
        """A failed attempt can be replaced with a new one while the booking's
        hold is still alive."""
        return self in (PaymentStatus.FAILED, PaymentStatus.CREATED, PaymentStatus.PENDING)


class PaymentMethod(StrEnum):
    """How the customer paid. Reported by the gateway, never chosen by us.

    Stored because refund behaviour differs sharply: a UPI refund lands in
    minutes, a card refund takes 5-7 working days, and telling a guest the
    wrong one is a support ticket a week later.
    """

    CARD = "card"
    UPI = "upi"
    NETBANKING = "netbanking"
    WALLET = "wallet"
    EMI = "emi"
    PAY_LATER = "paylater"
    UNKNOWN = "unknown"

    @classmethod
    def parse(cls, raw: str | None) -> PaymentMethod:
        """Unknown methods degrade rather than raise.

        Razorpay adds payment methods without warning, and a new one must not
        take down webhook processing for every payment.
        """
        try:
            return cls(str(raw or "").lower())
        except ValueError:
            return cls.UNKNOWN


class RefundSpeed(StrEnum):
    """``optimum`` costs a fee and lands in minutes on supported methods;
    ``normal`` is free and takes 5-7 working days.

    Chosen per refund rather than globally: an instant refund is worth paying
    for when the platform caused the cancellation, and not worth it when the
    guest simply changed their mind.
    """

    NORMAL = "normal"
    OPTIMUM = "optimum"


class RefundStatus(StrEnum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class TransactionKind(StrEnum):
    """Every distinct way money moves.

    The ledger records all of them, including the ones that are not payments —
    a chargeback fee and a gateway fee both reduce what the platform actually
    receives, and a reconciliation that ignores them never balances.
    """

    CHARGE = "charge"
    REFUND = "refund"
    CHARGEBACK = "chargeback"
    GATEWAY_FEE = "gateway_fee"
    GATEWAY_TAX = "gateway_tax"
    ADJUSTMENT = "adjustment"

    @property
    def is_credit(self) -> bool:
        """True when money comes *in* to the platform."""
        return self is TransactionKind.CHARGE


@dataclass(frozen=True, slots=True)
class GatewayOrderId:
    value: str

    def __post_init__(self) -> None:
        if not _ORDER_RE.match(self.value):
            msg = f"Not a Razorpay order id: {self.value!r}"
            raise ValueError(msg)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class GatewayPaymentId:
    value: str

    def __post_init__(self) -> None:
        if not _PAYMENT_RE.match(self.value):
            msg = f"Not a Razorpay payment id: {self.value!r}"
            raise ValueError(msg)

    def __str__(self) -> str:
        return self.value


def is_refund_id(value: str) -> bool:
    return bool(_REFUND_RE.match(value))


#: Razorpay caps a single order at ₹5,00,000 by default for most accounts.
#: Checked before the call so an over-limit booking fails with a message a
#: human can act on rather than a gateway error code.
MAX_ORDER_AMOUNT_MINOR: Final = 500_000_00

#: Razorpay's `receipt` field. Our booking reference, so a payment can be
#: matched to a booking from the Razorpay dashboard during an incident without
#: querying our database at all.
RECEIPT_MAX_LENGTH: Final = 40
