"""Razorpay signature verification.

**This is the only thing standing between the platform and free bookings.**
Everything a client tells us about a payment is attacker-controlled; the
signature is what makes a callback evidence rather than a claim.

Razorpay uses HMAC-SHA256 in two different places, with **two different
secrets**, and confusing them is the classic integration bug:

* **Checkout callback** — ``HMAC(order_id + "|" + payment_id, KEY_SECRET)``.
  Returned to the browser after payment. Proves the payment belongs to that
  order.
* **Webhook** — ``HMAC(raw_request_body, WEBHOOK_SECRET)``. Sent server-to-server
  in ``X-Razorpay-Signature``.

Two rules that are easy to get wrong and fatal to get wrong:

**Verify the RAW body, never re-serialised JSON.** ``json.dumps(await
request.json())`` produces different bytes — different key order, different
whitespace, different unicode escaping — and the HMAC will not match. Worse,
someone "fixing" that by loosening the check removes the protection entirely.

**Compare in constant time.** ``==`` on a hex digest short-circuits at the first
differing byte and leaks the matching prefix length through timing, which is
enough to forge a signature byte by byte given enough attempts.

Everything here is pure: no HTTP, no database, no clock. It is exercised
directly by ``tests/unit/payment/test_signature.py``.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Final

#: Razorpay signs with SHA-256 everywhere. Pinned rather than read from the
#: payload — an attacker-chosen algorithm is the "alg=none" of webhooks.
_ALGORITHM: Final = hashlib.sha256


class SignatureError(ValueError):
    """Verification failed.

    Carries no detail about *why*. "Bad length" versus "bad digest" tells an
    attacker which part of their forgery to fix next.
    """

    def __init__(self, context: str = "signature") -> None:
        self.context = context
        super().__init__("Signature verification failed")


def compute_hmac(payload: bytes, secret: str) -> str:
    """Hex HMAC-SHA256. The one place the primitive is used."""
    return hmac.new(secret.encode(), payload, _ALGORITHM).hexdigest()


def verify(payload: bytes, signature: str, secret: str, *, context: str = "signature") -> None:
    """Constant-time compare, or raise.

    Raises rather than returning a bool on purpose: a caller that forgets to
    check a returned ``False`` has an authentication bypass, and that mistake
    is invisible in review. A raise cannot be ignored by accident.
    """
    if not signature or not secret:
        raise SignatureError(context)

    expected = compute_hmac(payload, secret)
    if not hmac.compare_digest(expected, signature.strip()):
        raise SignatureError(context)


def verify_checkout(*, order_id: str, payment_id: str, signature: str, key_secret: str) -> None:
    """Verify the browser's post-payment callback.

    Signed over ``order_id|payment_id``, so it proves the payment belongs to
    *this* order. Without it a client could report any payment id — including
    a real one from a ₹1 order — against a ₹50,000 booking.

    Note this is signed with **KEY_SECRET**, not the webhook secret.
    """
    if not order_id or not payment_id:
        raise SignatureError("checkout")
    verify(f"{order_id}|{payment_id}".encode(), signature, key_secret, context="checkout")


def verify_webhook(*, raw_body: bytes, signature: str, webhook_secret: str) -> None:
    """Verify a webhook.

    ``raw_body`` must be the exact bytes Razorpay sent. See the module
    docstring — this is the single most common way a webhook integration is
    silently broken, and the "fix" people reach for removes the security.

    Signed with **WEBHOOK_SECRET**, which is configured separately from the API
    key precisely so that a leaked webhook secret cannot be used to call the
    API, and vice versa.
    """
    if not raw_body:
        raise SignatureError("webhook")
    verify(raw_body, signature, webhook_secret, context="webhook")


@dataclass(frozen=True, slots=True)
class CheckoutCallback:
    """What the browser posts back after a successful checkout.

    A value object rather than a dict so the three fields cannot be passed in
    the wrong order to :func:`verify_checkout` — which would silently produce a
    valid-looking failure and send everyone hunting for a config problem.
    """

    order_id: str
    payment_id: str
    signature: str

    def verify(self, key_secret: str) -> None:
        verify_checkout(
            order_id=self.order_id,
            payment_id=self.payment_id,
            signature=self.signature,
            key_secret=key_secret,
        )
