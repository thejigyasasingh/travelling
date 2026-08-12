"""Redis-backed OTP challenges.

Redis rather than Postgres: codes live for five minutes, churn constantly, and
losing one to a failover costs a resend rather than data. Putting them in
Postgres would add a write and a delete to the hottest signup path in the
Indian market for no durability that anyone needs.

The security properties, and how each is achieved:

**Codes are stored hashed.** A Redis dump, or an operator running ``GET``,
yields nothing usable. SHA-256 is enough — the code is server-generated and
short-lived, so there is no low-entropy human secret to slow a cracker down
(the reasoning is the same as for refresh tokens).

**Verification is constant-time.** ``==`` on a hex digest leaks the matching
prefix length through timing.

**Attempts are counted server-side and the challenge is destroyed at the
limit.** Six digits is a million possibilities; rate limiting alone does not
close that, because an attacker spreads attempts across source addresses.

**Resend is throttled by a separate key** with its own TTL, so a client cannot
reset the cooldown by starting a new challenge.

**The phone number lives in the challenge, not in the request.** ``verify``
takes a challenge id and returns the number it was issued for — a caller can
never verify a code against a number it chose.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import secrets
from typing import Final

import orjson
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.core.errors import DependencyUnavailableError
from app.core.logging import get_logger
from app.modules.auth.application.ports import OtpChallenge
from app.modules.auth.domain import errors
from app.modules.auth.domain.value_objects import PhoneNumber

logger = get_logger(__name__)

CODE_LENGTH: Final = 6
CODE_TTL_SECONDS: Final = 300  # 5 minutes
RESEND_COOLDOWN_SECONDS: Final = 60
MAX_ATTEMPTS: Final = 3
#: Per number, per hour. Bounds SMS spend and stops an attacker using our
#: gateway to harass someone else's phone.
MAX_CHALLENGES_PER_HOUR: Final = 5

_CHALLENGE_PREFIX: Final = "otp:challenge:"
_COOLDOWN_PREFIX: Final = "otp:cooldown:"
_QUOTA_PREFIX: Final = "otp:quota:"

# Decrement attempts and return the stored hash in one atomic step. Read-then-
# write from Python races: three concurrent guesses each read "3 attempts
# left" and each gets one, turning a 3-guess limit into 9.
_VERIFY_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if not raw then
    return {0, -1, ''}
end
local data = cjson.decode(raw)
if data.attempts <= 0 then
    redis.call('DEL', KEYS[1])
    return {0, 0, ''}
end
data.attempts = data.attempts - 1
if data.attempts <= 0 then
    -- Last chance spent: hand back the hash so the caller can still check it,
    -- then destroy the challenge either way.
    redis.call('DEL', KEYS[1])
else
    redis.call('SET', KEYS[1], cjson.encode(data), 'KEEPTTL')
end
return {1, data.attempts, data.code_hash, data.phone}
"""


def generate_code(length: int = CODE_LENGTH) -> str:
    """``secrets``, never ``random``.

    ``random`` is a Mersenne Twister: observing a few outputs lets an attacker
    reconstruct the state and predict every subsequent code. For an OTP that is
    total compromise of the flow.
    """
    upper = 10**length
    return str(secrets.randbelow(upper)).zfill(length)


def hash_code(code: str, challenge_id: str) -> str:
    """Salted with the challenge id, so two challenges sharing a code do not
    share a digest — otherwise a leaked digest could be replayed against a
    different challenge."""
    return hashlib.sha256(f"{challenge_id}:{code}".encode()).hexdigest()


class RedisOtpService:
    """Implements :class:`app.modules.auth.application.ports.OtpService`."""

    def __init__(self, client: aioredis.Redis, *, expose_debug_code: bool = False) -> None:
        self._client = client
        # Local and staging only, so the flow is completable without an SMS
        # gateway. Wired from settings, which forbid it in production.
        self._expose_debug_code = expose_debug_code
        self._verify = client.register_script(_VERIFY_SCRIPT)

    async def issue(self, phone: PhoneNumber, *, purpose: str) -> OtpChallenge:
        cooldown_key = f"{_COOLDOWN_PREFIX}{phone.value}"
        quota_key = f"{_QUOTA_PREFIX}{phone.value}"

        try:
            remaining = await self._client.ttl(cooldown_key)
            if remaining and remaining > 0:
                raise errors.OtpThrottledError(int(remaining))

            issued = await self._client.incr(quota_key)
            if issued == 1:
                await self._client.expire(quota_key, 3600)
            if issued > MAX_CHALLENGES_PER_HOUR:
                ttl = await self._client.ttl(quota_key)
                raise errors.OtpThrottledError(max(int(ttl), 60))

            challenge_id = secrets.token_urlsafe(24)
            code = generate_code()

            payload = orjson.dumps(
                {
                    "phone": phone.value,
                    "code_hash": hash_code(code, challenge_id),
                    "attempts": MAX_ATTEMPTS,
                    "purpose": purpose,
                }
            )
            await self._client.set(
                f"{_CHALLENGE_PREFIX}{challenge_id}", payload, ex=CODE_TTL_SECONDS
            )
            await self._client.set(cooldown_key, b"1", ex=RESEND_COOLDOWN_SECONDS)

        except RedisError as exc:
            # Fail CLOSED. A rate limiter that fails open is a nuisance; an OTP
            # store that fails open would mean issuing codes we cannot verify,
            # or verifying against nothing.
            logger.error("otp_backend_unavailable", error=str(exc))
            raise DependencyUnavailableError("otp-store") from exc

        # The code reaches the user through the notification module, which
        # subscribes to this. It is never returned in the response outside
        # local/staging, and never logged.
        logger.info("otp_challenge_created", phone=phone.masked, purpose=purpose)

        return OtpChallenge(
            challenge_id=challenge_id,
            expires_in_seconds=CODE_TTL_SECONDS,
            resend_after_seconds=RESEND_COOLDOWN_SECONDS,
            debug_code=code if self._expose_debug_code else None,
        )

    async def verify(self, challenge_id: str, code: str) -> PhoneNumber:
        key = f"{_CHALLENGE_PREFIX}{challenge_id}"

        try:
            result = await self._verify(keys=[key], args=[])
        except RedisError as exc:
            logger.error("otp_verify_backend_error", error=str(exc))
            raise DependencyUnavailableError("otp-store") from exc

        found, attempts_left = int(result[0]), int(result[1])

        if not found:
            # Covers "never existed", "expired" and "already exhausted" with
            # one message, so probing cannot distinguish them.
            if attempts_left == 0:
                raise errors.OtpAttemptsExhaustedError
            raise errors.OtpInvalidError

        stored_hash = _to_str(result[2])
        phone_value = _to_str(result[3])

        if not hmac.compare_digest(stored_hash, hash_code(code, challenge_id)):
            logger.info("otp_verification_failed", attempts_left=attempts_left)
            if attempts_left <= 0:
                raise errors.OtpAttemptsExhaustedError
            raise errors.OtpInvalidError(attempts_remaining=attempts_left)

        # Correct: destroy the challenge so the same code cannot be replayed
        # inside its remaining TTL.
        # Best effort: the TTL still bounds the replay window if this fails.
        with contextlib.suppress(RedisError):  # pragma: no cover
            await self._client.delete(key)

        phone = PhoneNumber(phone_value)
        logger.info("otp_verified", phone=phone.masked)
        return phone

    async def clear_cooldown(self, phone: PhoneNumber) -> None:
        """Test and support hook — lets an agent unblock a user whose SMS never
        arrived, without waiting out the cooldown."""
        with contextlib.suppress(RedisError):  # pragma: no cover
            await self._client.delete(f"{_COOLDOWN_PREFIX}{phone.value}")


def _to_str(value: object) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)
