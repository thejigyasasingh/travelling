"""Auth value objects.

Validation lives here rather than in a pydantic schema for one reason: a
pydantic model only guards the *HTTP* door. A user created by the admin CLI, a
seed script or a data migration must obey the same rules, and a rule that only
runs on one code path is a rule you do not actually have.

The interface layer still validates — it produces better error messages and
rejects nonsense before a use case starts — but it is a convenience, not the
authority.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Final, Self

# Deliberately permissive. RFC 5322 is far more baroque than this, and the
# strict regexes people copy from the internet reject valid addresses — which
# is a worse failure than accepting one that bounces. The real proof that an
# address exists is the verification email.
_EMAIL_RE: Final = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}$")
MAX_EMAIL_LENGTH: Final = 254  # RFC 5321 path limit

_E164_RE: Final = re.compile(r"^\+[1-9]\d{7,14}$")

MIN_PASSWORD_LENGTH: Final = 10
MAX_PASSWORD_LENGTH: Final = 128

# Substrings that make a password trivially guessable in *this* product's
# context. A full breach-corpus check (HIBP k-anonymity) belongs in the
# registration use case where an outbound call is acceptable; this is the
# offline floor.
_BANNED_FRAGMENTS: Final = frozenset(
    {
        "password",
        "passw0rd",
        "qwerty",
        "12345678",
        "letmein",
        "welcome",
        "admin",
        "roaming",
        "wandering",
        "travel",
    }
)


class InvalidEmailError(ValueError):
    pass


class InvalidPhoneNumberError(ValueError):
    pass


class WeakPasswordError(ValueError):
    """Carries every failed requirement at once.

    Returning them one at a time turns choosing a password into a guessing
    game where the user fixes one rule and discovers the next.
    """

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


@dataclass(frozen=True, slots=True)
class Email:
    """Normalised, case-insensitive email address.

    Stored lowercase and matched by a ``citext`` column, so ``Priya@x.com`` and
    ``priya@x.com`` cannot become two accounts — which is both a support
    nightmare and an account-takeover vector during password reset.

    Gmail-style dot and ``+tag`` stripping is deliberately **not** done.
    ``a.b@gmail.com`` and ``ab@gmail.com`` are the same Google inbox, but
    normalising them would silently merge identities on providers where they
    are genuinely different addresses, and users legitimately use ``+tags`` to
    keep accounts apart.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise InvalidEmailError("Email is required")
        if len(self.value) > MAX_EMAIL_LENGTH:
            raise InvalidEmailError(f"Email must be at most {MAX_EMAIL_LENGTH} characters")
        if not _EMAIL_RE.match(self.value):
            raise InvalidEmailError("Email is not a valid address")

    @classmethod
    def parse(cls, raw: str) -> Self:
        # NFKC first: visually identical Unicode forms must not produce two
        # distinct rows that look the same to a human reviewing them.
        normalised = unicodedata.normalize("NFKC", raw).strip().lower()
        return cls(normalised)

    @property
    def domain(self) -> str:
        return self.value.rpartition("@")[2]

    @property
    def masked(self) -> str:
        """For logs, support tooling and "we sent a link to p****@x.com"."""
        local, _, domain = self.value.partition("@")
        return f"{local[0]}{'*' * max(len(local) - 1, 1)}@{domain}"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PhoneNumber:
    """E.164 only. No local formats, ever.

    ``98765 43210`` is meaningless without knowing the country, and storing
    mixed formats makes "is this the same number?" unanswerable — which breaks
    OTP delivery and lets one person register twice.
    """

    value: str

    def __post_init__(self) -> None:
        if not _E164_RE.match(self.value):
            raise InvalidPhoneNumberError(
                "Phone number must be in E.164 format, e.g. +919876543210"
            )

    @classmethod
    def parse(cls, raw: str, *, default_country_code: str = "+91") -> Self:
        """Accepts what users actually type; stores one canonical form."""
        cleaned = re.sub(r"[\s\-()./]", "", raw.strip())
        if cleaned.startswith("00"):
            cleaned = "+" + cleaned[2:]
        if not cleaned.startswith("+"):
            # A bare 10-digit number is the overwhelmingly common Indian case.
            cleaned = default_country_code + cleaned.lstrip("0")
        return cls(cleaned)

    @property
    def masked(self) -> str:
        return f"{self.value[:3]}{'*' * (len(self.value) - 7)}{self.value[-4:]}"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class RawPassword:
    """A plaintext password that has passed policy, and nothing more.

    It exists so a function signature can say "this has been checked" and so
    an unchecked ``str`` cannot be hashed by accident. It is never persisted,
    never logged (``__repr__`` is overridden), and never leaves the use case
    that created it.

    The policy follows NIST SP 800-63B: **length over composition**. Mandatory
    symbol/digit/case rules push users toward `Password1!` — predictable to a
    cracker, hard for a human — so the floor here is length plus a check
    against the obvious dictionary, not a character-class matrix.
    """

    value: str

    def __post_init__(self) -> None:
        reasons: list[str] = []

        if len(self.value) < MIN_PASSWORD_LENGTH:
            reasons.append(f"must be at least {MIN_PASSWORD_LENGTH} characters")
        if len(self.value) > MAX_PASSWORD_LENGTH:
            # Argon2 hashes the whole input; an unbounded password is a cheap
            # CPU-exhaustion vector.
            reasons.append(f"must be at most {MAX_PASSWORD_LENGTH} characters")
        if self.value != self.value.strip():
            # Leading/trailing whitespace is almost always a copy-paste
            # accident that locks the user out on their next sign-in.
            reasons.append("must not begin or end with whitespace")

        lowered = self.value.lower()
        if any(fragment in lowered for fragment in _BANNED_FRAGMENTS):
            reasons.append("must not contain a common or product-related word")
        if len(set(self.value)) < 5:
            reasons.append("must not repeat the same few characters")

        if reasons:
            raise WeakPasswordError(reasons)

    def contains_identity(self, *identifiers: str) -> bool:
        """True if the password embeds the user's own email or name.

        Checked by the use case, which is the only place that knows who is
        registering.
        """
        lowered = self.value.lower()
        for identifier in identifiers:
            if not identifier:
                continue
            local = identifier.lower().partition("@")[0]
            if len(local) >= 4 and local in lowered:
                return True
        return False

    def __repr__(self) -> str:  # pragma: no cover
        return "RawPassword(***)"

    def __str__(self) -> str:  # pragma: no cover
        return "***"
