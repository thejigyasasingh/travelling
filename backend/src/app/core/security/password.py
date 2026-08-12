"""Password hashing.

Argon2id, not bcrypt. bcrypt is memory-light, so a GPU farm runs it massively
in parallel; Argon2id's memory cost (64 MiB per hash here) makes that
uneconomic. It won the Password Hashing Competition and is the OWASP default.

Two properties this module guarantees that a bare ``argon2.PasswordHasher``
does not:

* **Constant-ish verification time on a missing user.** ``verify()`` on an
  unknown email must burn the same CPU as a real check, or response timing
  tells an attacker which emails are registered.
* **Transparent rehash on parameter upgrade.** When we raise the cost
  parameters, existing users are migrated on their next successful login
  rather than being locked out or left on weak hashes forever.
"""

from __future__ import annotations

import contextlib
from typing import Final

from argon2 import PasswordHasher
from argon2 import exceptions as argon2_exc
from argon2.low_level import Type

from app.core.config import SecuritySettings

# Argon2id: hybrid resistance to both GPU and side-channel attacks.
_HASH_TYPE: Final = Type.ID
_SALT_BYTES: Final = 16
_HASH_BYTES: Final = 32

# A real Argon2id hash of a value nobody knows. Verifying against this on a
# missing user costs exactly what a genuine verification costs.
_DUMMY_HASH: Final = (
    "$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHRzb21lc2E$Yy1QAdlL8mkKPRJXi2h0oCbYKrFDF9YsKlvQ0Jjy1sQ"
)

MIN_PASSWORD_LENGTH: Final = 10
MAX_PASSWORD_LENGTH: Final = 128  # Argon2 hashes the whole input; cap the DoS surface


class PasswordHashError(RuntimeError):
    """Hashing itself failed — memory pressure, not a wrong password."""


class PasswordHasherService:
    """Wraps argon2-cffi with our policy. One instance, held by the container."""

    __slots__ = ("_hasher",)

    def __init__(self, settings: SecuritySettings) -> None:
        self._hasher = PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_kib,
            parallelism=settings.argon2_parallelism,
            hash_len=_HASH_BYTES,
            salt_len=_SALT_BYTES,
            type=_HASH_TYPE,
        )

    def hash(self, password: str) -> str:
        self._validate_length(password)
        try:
            return self._hasher.hash(password)
        except argon2_exc.HashingError as exc:  # pragma: no cover — OOM path
            raise PasswordHashError("Password hashing failed") from exc

    def verify(self, password: str, stored_hash: str | None) -> bool:
        """``stored_hash=None`` means "no such user" — still does the work.

        Returning early here would make a nonexistent account measurably faster
        to probe than an existing one, which is a free user-enumeration oracle
        on the login endpoint.
        """
        if stored_hash is None:
            self._burn()
            return False
        try:
            return self._hasher.verify(stored_hash, password)
        except (argon2_exc.VerifyMismatchError, argon2_exc.InvalidHashError):
            return False
        except argon2_exc.VerificationError:
            return False

    def needs_rehash(self, stored_hash: str) -> bool:
        """True when the hash predates a cost-parameter increase. Callers
        rehash inside the successful-login path, where the plaintext is in
        hand and the extra work is already budgeted."""
        try:
            return self._hasher.check_needs_rehash(stored_hash)
        except argon2_exc.InvalidHashError:
            return True  # unrecognisable format: force a rewrite

    def _burn(self) -> None:
        # The mismatch IS the expected outcome; only the CPU spent matters.
        with contextlib.suppress(Exception):
            self._hasher.verify(_DUMMY_HASH, "timing-equalisation")

    @staticmethod
    def _validate_length(password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            msg = f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
            raise ValueError(msg)
        if len(password) > MAX_PASSWORD_LENGTH:
            msg = f"Password must be at most {MAX_PASSWORD_LENGTH} characters"
            raise ValueError(msg)
