"""Email, phone and password policy."""

from __future__ import annotations

import pytest

from app.modules.auth.domain.value_objects import (
    Email,
    InvalidEmailError,
    InvalidPhoneNumberError,
    PhoneNumber,
    RawPassword,
    WeakPasswordError,
)

pytestmark = pytest.mark.unit


class TestEmail:
    def test_normalises_case_and_whitespace(self) -> None:
        # Priya@X.com and priya@x.com must not become two accounts — that is
        # both a support nightmare and a password-reset takeover vector.
        assert Email.parse("  Priya@Example.COM ").value == "priya@example.com"

    def test_unicode_is_normalised(self) -> None:
        # Visually identical forms must not produce two distinct rows.
        assert Email.parse("ﬁrst@example.com").value == "first@example.com"

    def test_plus_tags_are_preserved(self) -> None:
        # Users legitimately keep accounts apart with +tags; stripping them
        # would silently merge identities.
        assert Email.parse("priya+travel@example.com").value == "priya+travel@example.com"

    def test_dots_are_preserved(self) -> None:
        assert Email.parse("a.b@gmail.com").value == "a.b@gmail.com"

    @pytest.mark.parametrize(
        "bad", ["", "not-an-email", "@example.com", "a@b", "a b@example.com", "a@@b.com"]
    )
    def test_rejects_malformed(self, bad: str) -> None:
        with pytest.raises(InvalidEmailError):
            Email.parse(bad)

    def test_rejects_over_length(self) -> None:
        with pytest.raises(InvalidEmailError):
            Email.parse("x" * 250 + "@example.com")

    def test_masking_keeps_the_domain(self) -> None:
        # Enough to tell a Gmail user from a corporate one; not enough to
        # identify the person.
        assert Email.parse("priya@example.com").masked == "p****@example.com"

    def test_domain_accessor(self) -> None:
        assert Email.parse("a@sub.example.com").domain == "sub.example.com"

    def test_is_immutable(self) -> None:
        with pytest.raises((AttributeError, TypeError)):
            Email.parse("a@b.com").value = "c@d.com"  # type: ignore[misc]


class TestPhoneNumber:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("+919876543210", "+919876543210"),
            ("9876543210", "+919876543210"),  # bare Indian number
            ("+91 98765 43210", "+919876543210"),
            ("+91-98765-43210", "+919876543210"),
            ("00919876543210", "+919876543210"),
            ("09876543210", "+919876543210"),  # trunk prefix stripped
            ("+1 (415) 555-0132", "+14155550132"),
        ],
    )
    def test_parses_what_users_actually_type(self, raw: str, expected: str) -> None:
        assert PhoneNumber.parse(raw).value == expected

    @pytest.mark.parametrize("bad", ["123", "+0123456789", "abcdefghij", "+"])
    def test_rejects_unusable(self, bad: str) -> None:
        with pytest.raises(InvalidPhoneNumberError):
            PhoneNumber.parse(bad)

    def test_masking_keeps_country_and_last_four(self) -> None:
        assert PhoneNumber("+919876543210").masked == "+91******3210"

    def test_only_e164_is_constructible_directly(self) -> None:
        with pytest.raises(InvalidPhoneNumberError):
            PhoneNumber("9876543210")


class TestPasswordPolicy:
    def test_accepts_a_long_memorable_passphrase(self) -> None:
        # NIST SP 800-63B: length over composition. No symbol is required.
        assert RawPassword("correct horse battery staple").value

    def test_rejects_short(self) -> None:
        with pytest.raises(WeakPasswordError, match="at least"):
            RawPassword("short1")

    def test_rejects_over_length(self) -> None:
        # Argon2 hashes the whole input; unbounded length is a CPU-exhaustion
        # vector.
        with pytest.raises(WeakPasswordError, match="at most"):
            RawPassword("a1B" * 100)

    def test_rejects_surrounding_whitespace(self) -> None:
        # Almost always a copy-paste accident that locks the user out on their
        # next sign-in.
        with pytest.raises(WeakPasswordError, match="whitespace"):
            RawPassword("  valid passphrase  ")

    @pytest.mark.parametrize(
        "bad", ["password123", "Passw0rd!!!", "qwerty12345", "roamingwandering1"]
    )
    def test_rejects_obvious_and_product_related(self, bad: str) -> None:
        with pytest.raises(WeakPasswordError, match="common"):
            RawPassword(bad)

    def test_rejects_low_character_variety(self) -> None:
        with pytest.raises(WeakPasswordError, match="repeat"):
            RawPassword("abababababab")

    def test_reports_every_failure_at_once(self) -> None:
        # Fixing one rule and discovering the next is how users end up choosing
        # Password1! — the exact thing this policy avoids.
        with pytest.raises(WeakPasswordError) as exc:
            RawPassword("  pass  ")
        assert len(exc.value.reasons) > 1

    def test_detects_the_users_own_identity(self) -> None:
        assert RawPassword("quiet-mountain-lake").contains_identity("priya@example.com") is False
        assert RawPassword("myprivate-priya-vault").contains_identity("priya@example.com")

    def test_identity_check_ignores_short_locals(self) -> None:
        # A 3-character local part would match inside almost any password.
        assert not RawPassword("abc-defghij-klm").contains_identity("abc@example.com")

    def test_never_reveals_itself_in_repr_or_str(self) -> None:
        # Passwords end up in tracebacks and log lines otherwise.
        password = RawPassword("correct horse battery")
        assert "correct" not in repr(password)
        assert "correct" not in str(password)
