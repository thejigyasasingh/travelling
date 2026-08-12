"""PII redaction.

This is a compliance control, not a nicety. Logs are retained for 90 days and
are readable by more people than production data is. Every one of these cases
has leaked from a real system somewhere.
"""

from __future__ import annotations

import pytest

from app.core.logging import scrub_pii

pytestmark = pytest.mark.unit


def scrub(**event: object) -> dict[str, object]:
    return dict(scrub_pii(None, "info", event))  # type: ignore[arg-type]


class TestSecretRedaction:
    @pytest.mark.parametrize(
        "key",
        ["password", "refresh_token", "authorization", "cvv", "api_key", "aadhaar", "otp"],
    )
    def test_secret_keys_are_removed(self, key: str) -> None:
        assert scrub(**{key: "sensitive"})[key] == "[REDACTED]"

    def test_key_matching_is_case_insensitive(self) -> None:
        # Header dicts arrive with mixed casing.
        assert scrub(Authorization="Bearer x")["Authorization"] == "[REDACTED]"

    def test_nested_secrets_are_removed(self) -> None:
        out = scrub(request={"body": {"password": "hunter2", "email": "a@b.com"}})
        body = out["request"]["body"]  # type: ignore[index]
        assert body["password"] == "[REDACTED]"

    def test_secrets_inside_lists(self) -> None:
        out = scrub(users=[{"password": "x"}, {"password": "y"}])
        assert all(u["password"] == "[REDACTED]" for u in out["users"])  # type: ignore[union-attr]


class TestMasking:
    def test_email_keeps_domain_for_debugging(self) -> None:
        # Enough to tell a Gmail user from a corporate one; not enough to
        # identify the person.
        # First character kept, the rest of the local part starred out.
        assert scrub(email="priya.sharma@example.com")["email"] == "p***********@example.com"

    def test_phone_keeps_last_four(self) -> None:
        assert scrub(phone="+91 98765 43210")["phone"] == "***3210"

    def test_malformed_email_is_fully_redacted(self) -> None:
        assert scrub(email="not-an-email")["email"] == "[REDACTED]"


class TestPatternScrubbing:
    """Catches secrets that arrive in a *value* rather than under a known key —
    the case where someone logs a whole request body while debugging."""

    def test_card_number_in_free_text(self) -> None:
        out = scrub(message="charging card 4111 1111 1111 1111 now")
        assert "4111" not in str(out["message"])

    def test_jwt_in_free_text(self) -> None:
        token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmno"
        out = scrub(message=f"token was {token}")
        assert "eyJ" not in str(out["message"])


class TestSafety:
    def test_ordinary_fields_survive(self) -> None:
        # Over-redaction makes logs useless, which leads to redaction being
        # switched off. Only what must go, goes.
        out = scrub(booking_id="bk_123", status="confirmed", amount_minor=250000)
        assert out == {"booking_id": "bk_123", "status": "confirmed", "amount_minor": 250000}

    def test_deep_nesting_is_truncated_not_recursed_forever(self) -> None:
        payload: dict[str, object] = {"level": 0}
        current = payload
        for i in range(1, 20):
            child: dict[str, object] = {"level": i}
            current["child"] = child
            current = child

        out = scrub(**payload)  # must not blow the stack
        assert out is not None
