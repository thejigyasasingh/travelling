"""Rate limiting middleware.

The counting algorithm lives in ``infrastructure/cache/rate_limiter.py``. This
file is the *policy*: who gets counted, in which bucket, at what limit, and
what happens when Redis is unavailable.

**Identity beats IP where possible.** Rate limiting an authenticated user by
IP punishes everyone behind one corporate NAT or one mobile carrier gateway —
in India that can be tens of thousands of legitimate users on a single address.
Authenticated requests are bucketed by user id; only anonymous traffic falls
back to IP.

**Per-route policies, not one global number.** ``GET /search`` at 60/min and
``POST /auth/login`` at 5 per 15 minutes are protecting against completely
different things: one is cost control, the other is credential stuffing. A
single global limit is either too loose for login or too tight for browsing.

**Auth endpoints fail closed; everything else fails open.** See the
``fail_open`` reasoning in the rate limiter module — a Redis outage must not
take the API down, but it also must not silently remove the only brake on
password guessing.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.core.config import Settings
from app.core.errors import ErrorCode
from app.core.logging import get_logger
from app.core.privacy import client_fingerprint, client_ip_from_headers
from app.infrastructure.cache.rate_limiter import RedisRateLimiter

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RatePolicy:
    limit: int
    window_seconds: int
    fail_open: bool = True
    #: Bucket by IP even when authenticated — for login, where the user is not
    #: yet identified and the attacker controls which account they target.
    by_ip: bool = False


# Longest-prefix wins; order is irrelevant.
def build_policies(settings: Settings) -> dict[str, RatePolicy]:
    rl = settings.ratelimit
    return {
        "/api/v1/auth/login": RatePolicy(rl.login_per_15min, 900, fail_open=False, by_ip=True),
        "/api/v1/auth/register": RatePolicy(10, 3600, fail_open=False, by_ip=True),
        "/api/v1/auth/refresh": RatePolicy(60, 3600, fail_open=False),
        "/api/v1/auth/password/forgot": RatePolicy(3, 3600, fail_open=False, by_ip=True),
        "/api/v1/auth/otp/request": RatePolicy(rl.otp_per_hour, 3600, fail_open=False, by_ip=True),
        # Verify is limited far more tightly than request: the OTP store itself
        # only allows 3 guesses per challenge, so anything above a handful of
        # calls is someone cycling challenges to brute-force a 6-digit code.
        "/api/v1/auth/otp/verify": RatePolicy(20, 3600, fail_open=False, by_ip=True),
        "/api/v1/auth/google": RatePolicy(30, 3600, fail_open=False, by_ip=True),
        "/api/v1/auth/email/resend": RatePolicy(5, 3600, fail_open=False),
        "/api/v1/auth/password/change": RatePolicy(10, 3600, fail_open=False),
        "/api/v1/search": RatePolicy(rl.search_anon_per_minute, 60),
        "/api/v1/bookings": RatePolicy(rl.booking_per_hour, 3600),
        "/api/v1/payments": RatePolicy(20, 3600, fail_open=False),
    }


# Paths that must never be throttled: a rate-limited health check gets the pod
# killed by Kubernetes, and a rate-limited payment webhook makes the gateway
# retry and eventually give up on a real payment.
_EXEMPT = re.compile(r"^/(health|metrics|docs|redoc|openapi\.json)")
_WEBHOOK = re.compile(r"^/api/v\d+/webhooks/")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Reads its limiter from the container on ``app.state``.

    Middleware is constructed while the app is being built, but the Redis pool
    it needs does not exist until the lifespan runs. Resolving the limiter per
    request rather than at construction keeps that ordering honest — the
    alternative is reaching into Starlette's unbuilt middleware stack to patch
    a constructor argument after the fact, which depends on framework
    internals and breaks silently when they change.
    """

    def __init__(self, app: object, *, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._settings = settings
        self._policies = build_policies(settings)
        self._enabled = settings.ratelimit.enabled
        salt = settings.observability.ip_hash_salt
        self._salt = salt.get_secret_value() if salt else ""

    @staticmethod
    def _limiter_for(request: Request) -> RedisRateLimiter | None:
        container = getattr(request.app.state, "container", None)
        return getattr(container, "rate_limiter", None)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if not self._enabled or _EXEMPT.match(path) or _WEBHOOK.match(path):
            return await call_next(request)

        limiter = self._limiter_for(request)
        if limiter is None:  # pragma: no cover — only before lifespan startup
            return await call_next(request)

        policy = self._policy_for(path, request.method)
        identity = self._identity(request, policy)

        result = await limiter.check(
            identity,
            limit=policy.limit,
            window_seconds=policy.window_seconds,
            fail_open=policy.fail_open and self._settings.ratelimit.fail_open,
        )

        if not result.allowed:
            logger.info(
                "rate_limited",
                path=path,
                identity_kind=identity.split(":", 1)[0],
                limit=policy.limit,
            )
            return JSONResponse(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                headers=result.headers(),
                content={
                    "error": {
                        "code": ErrorCode.RATE_LIMITED,
                        "message": "Too many requests. Please slow down.",
                        "details": {"retry_after_seconds": result.retry_after},
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )

        response = await call_next(request)
        # Headers on success too — clients should be able to back off before
        # they are throttled, not only after.
        for key, value in result.headers().items():
            response.headers.setdefault(key, value)
        return response

    def _policy_for(self, path: str, method: str) -> RatePolicy:
        for prefix, policy in self._policies.items():
            if path.startswith(prefix):
                # Reads of a collection are cheap; writes to it are not.
                if method == "GET" and policy.window_seconds >= 3600:
                    break
                return policy
        rl = self._settings.ratelimit
        return RatePolicy(rl.user_per_minute, 60)

    def _identity(self, request: Request, policy: RatePolicy) -> str:
        if not policy.by_ip:
            user_id = getattr(request.state, "user_id", None)
            if user_id:
                return f"user:{user_id}"
        return f"ip:{self._client_ip(request)}"

    def _client_ip(self, request: Request) -> str:
        """A fingerprint, never the address.

        The bucket key reaches Redis and log lines, and an IP is personal data
        under the GDPR and DPDP. This used to hash inline here — correctly —
        while the access log wrote the raw value on every request. One shared
        helper now, in `core/privacy.py`, so the two cannot drift again.
        """
        return client_fingerprint(
            client_ip_from_headers(
                request.headers.get("x-forwarded-for"),
                request.client.host if request.client else None,
            ),
            salt=self._salt,
        )
