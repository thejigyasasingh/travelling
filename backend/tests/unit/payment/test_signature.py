"""Signature verification.

This is the security boundary of the whole payment module: it is the only thing
standing between the platform and free bookings. A failure in this file is a
vulnerability, not a bug.

What is asserted here, and why each one matters:

* the two secrets are genuinely separate — mixing them is the classic Razorpay
  integration bug, and the "fix" people reach for is to stop verifying;
* verification is over the **raw bytes**, so re-serialised JSON fails;
* tampering with any part of a payload fails;
* verification **raises** rather than returning a falsy value, so a caller
  cannot forget to check it.
"""

from __future__ import annotations

import json

import pytest

from app.modules.payment.domain.signature import (
    CheckoutCallback,
    SignatureError,
    compute_hmac,
    verify,
    verify_checkout,
    verify_webhook,
)

pytestmark = pytest.mark.unit

KEY_SECRET = "rzp_key_secret_value"
WEBHOOK_SECRET = "rzp_webhook_secret_value"

ORDER_ID = "order_MkL9pQrStUvWxY"
PAYMENT_ID = "pay_MkL9pQrStUvWxZ"


def checkout_signature(order_id: str = ORDER_ID, payment_id: str = PAYMENT_ID) -> str:
    """Exactly what Razorpay computes: HMAC over ``order_id|payment_id``."""
    return compute_hmac(f"{order_id}|{payment_id}".encode(), KEY_SECRET)


def webhook_signature(body: bytes) -> str:
    return compute_hmac(body, WEBHOOK_SECRET)


# ══════════════════════════════════════════════════════════════════════════
# Checkout callback
# ══════════════════════════════════════════════════════════════════════════


def test_genuine_checkout_callback_verifies() -> None:
    verify_checkout(
        order_id=ORDER_ID,
        payment_id=PAYMENT_ID,
        signature=checkout_signature(),
        key_secret=KEY_SECRET,
    )


def test_payment_id_swapped_for_another_fails() -> None:
    """The attack the checkout signature exists to stop.

    A client pays ₹1 on one order and reports that payment id against a ₹50,000
    booking. The signature covers *both* ids together, so the pair no longer
    matches.
    """
    with pytest.raises(SignatureError):
        verify_checkout(
            order_id=ORDER_ID,
            payment_id="pay_SomeOtherCheapOne",
            signature=checkout_signature(),
            key_secret=KEY_SECRET,
        )


def test_order_id_swapped_fails() -> None:
    with pytest.raises(SignatureError):
        verify_checkout(
            order_id="order_ADifferentOrder",
            payment_id=PAYMENT_ID,
            signature=checkout_signature(),
            key_secret=KEY_SECRET,
        )


def test_checkout_signed_with_the_webhook_secret_fails() -> None:
    """The two secrets are not interchangeable.

    If this ever passes, someone has collapsed them into one value and a leaked
    webhook secret now authenticates API-equivalent callbacks.
    """
    forged = compute_hmac(f"{ORDER_ID}|{PAYMENT_ID}".encode(), WEBHOOK_SECRET)
    with pytest.raises(SignatureError):
        verify_checkout(
            order_id=ORDER_ID,
            payment_id=PAYMENT_ID,
            signature=forged,
            key_secret=KEY_SECRET,
        )


@pytest.mark.parametrize(
    "signature",
    [
        "",
        "not-hex-at-all",
        # Correct length, wrong content — length alone must never be the check.
        "0" * 64,
        # A valid signature with one byte flipped.
        checkout_signature()[:-1] + ("0" if checkout_signature()[-1] != "0" else "1"),
    ],
)
def test_malformed_and_near_miss_signatures_fail(signature: str) -> None:
    with pytest.raises(SignatureError):
        verify_checkout(
            order_id=ORDER_ID,
            payment_id=PAYMENT_ID,
            signature=signature,
            key_secret=KEY_SECRET,
        )


def test_empty_ids_are_refused_before_hashing() -> None:
    """An empty id would otherwise hash to a stable, forgeable value."""
    with pytest.raises(SignatureError):
        verify_checkout(
            order_id="", payment_id=PAYMENT_ID, signature="x" * 64, key_secret=KEY_SECRET
        )
    with pytest.raises(SignatureError):
        verify_checkout(order_id=ORDER_ID, payment_id="", signature="x" * 64, key_secret=KEY_SECRET)


def test_surrounding_whitespace_is_tolerated() -> None:
    """Some proxies pad header values. The digest is what matters."""
    verify_checkout(
        order_id=ORDER_ID,
        payment_id=PAYMENT_ID,
        signature=f"  {checkout_signature()}\n",
        key_secret=KEY_SECRET,
    )


def test_checkout_callback_value_object_matches_the_function() -> None:
    """The value object exists so the three strings cannot be passed in the
    wrong order — which would look like a config problem, not a bug."""
    callback = CheckoutCallback(
        order_id=ORDER_ID, payment_id=PAYMENT_ID, signature=checkout_signature()
    )
    callback.verify(KEY_SECRET)

    with pytest.raises(SignatureError):
        CheckoutCallback(
            order_id=PAYMENT_ID, payment_id=ORDER_ID, signature=checkout_signature()
        ).verify(KEY_SECRET)


# ══════════════════════════════════════════════════════════════════════════
# Webhooks
# ══════════════════════════════════════════════════════════════════════════

BODY = (
    b'{"event":"payment.captured","payload":{"payment":{"entity":'
    b'{"id":"pay_MkL9pQrStUvWxZ","amount":4500000,"currency":"INR","captured":true}}}}'
)


def test_genuine_webhook_verifies() -> None:
    verify_webhook(raw_body=BODY, signature=webhook_signature(BODY), webhook_secret=WEBHOOK_SECRET)


def test_reserialised_json_fails() -> None:
    """**The** webhook integration bug.

    ``json.dumps(await request.json())`` round-trips to different bytes — key
    order, whitespace, unicode escaping — so the HMAC no longer matches. When
    this test fails, the handler has started parsing before verifying, and the
    tempting "fix" is to stop verifying.
    """
    signature = webhook_signature(BODY)
    reserialised = json.dumps(json.loads(BODY)).encode()

    assert reserialised != BODY, "the fixture must actually change under a round trip"
    with pytest.raises(SignatureError):
        verify_webhook(raw_body=reserialised, signature=signature, webhook_secret=WEBHOOK_SECRET)


def test_a_single_flipped_byte_in_the_body_fails() -> None:
    """The forgery that matters: change the amount, keep the signature."""
    signature = webhook_signature(BODY)
    tampered = BODY.replace(b"4500000", b"0000001")

    with pytest.raises(SignatureError):
        verify_webhook(raw_body=tampered, signature=signature, webhook_secret=WEBHOOK_SECRET)


def test_webhook_signed_with_the_key_secret_fails() -> None:
    forged = compute_hmac(BODY, KEY_SECRET)
    with pytest.raises(SignatureError):
        verify_webhook(raw_body=BODY, signature=forged, webhook_secret=WEBHOOK_SECRET)


def test_empty_body_is_refused() -> None:
    with pytest.raises(SignatureError):
        verify_webhook(
            raw_body=b"",
            signature=compute_hmac(b"", WEBHOOK_SECRET),
            webhook_secret=WEBHOOK_SECRET,
        )


def test_empty_secret_is_refused() -> None:
    """A deployment with an unset webhook secret must reject everything.

    The dangerous failure mode is the opposite: ``HMAC(body, "")`` is a
    perfectly computable value, so an attacker who knows the secret is unset can
    sign their own webhooks.
    """
    with pytest.raises(SignatureError):
        verify(BODY, compute_hmac(BODY, ""), "")


# ══════════════════════════════════════════════════════════════════════════


def test_verification_raises_rather_than_returning_a_flag() -> None:
    """A caller that forgets to check a returned ``False`` has an
    authentication bypass, and that mistake is invisible in review."""
    assert verify(BODY, webhook_signature(BODY), WEBHOOK_SECRET) is None


def test_error_carries_no_detail_about_why() -> None:
    """ "Bad length" versus "bad digest" tells an attacker which part of their
    forgery to fix next."""
    with pytest.raises(SignatureError) as exc:
        verify(BODY, "0" * 64, WEBHOOK_SECRET)
    assert str(exc.value) == "Signature verification failed"
