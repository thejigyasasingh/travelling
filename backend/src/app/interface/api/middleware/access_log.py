"""Access logging and HTTP metrics.

Replaces ``uvicorn.access`` (silenced in ``core/logging.py``), which emits an
unstructured line with no correlation ID, no user, and no duration bucket —
useless for anything beyond eyeballing a dev terminal.

What is logged and why:

* **The route template, not the raw path.** ``/api/v1/bookings/{booking_id}``,
  never ``/api/v1/bookings/9f3a...``. As a metric label the raw path is an
  unbounded cardinality explosion that will kill Prometheus; as a log field it
  is an ID scattered across millions of lines.
* **Query strings are dropped entirely.** They carry tokens in password-reset
  links, emails in search filters, and coordinates.
* **Slow requests are logged at WARNING** with a threshold from config, so the
  latency tail is visible without sampling traces.
* **5xx logs the exception; 4xx does not.** A client sending bad input is not
  an error worth a stack trace.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.privacy import client_fingerprint, client_ip_from_headers, network_prefix

logger = get_logger("http.access")

# Buckets chosen around our SLOs (p95 < 300 ms for reads, < 1 s for writes),
# not the library defaults — a histogram whose buckets straddle the target
# cannot tell you whether you met it.
_LATENCY_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 2.0, 5.0, 10.0)

http_requests_total = Counter(
    "http_requests_total",
    "HTTP requests",
    labelnames=("method", "route", "status"),
)
http_request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    labelnames=("method", "route"),
    buckets=_LATENCY_BUCKETS,
)
http_requests_received = Counter(
    "http_requests_received_total",
    "Requests entering the handler chain (counted before the response exists)",
    labelnames=("method",),
)


class AccessLogMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._slow_ms = settings.observability.slow_request_ms
        self._metrics_enabled = settings.observability.metrics_enabled
        salt = settings.observability.ip_hash_salt
        self._salt = salt.get_secret_value() if salt else ""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        method = request.method
        if self._metrics_enabled:
            http_requests_received.labels(method=method).inc()

        try:
            response = await call_next(request)
        except Exception:
            # The exception handler will convert this to a 500; record it here
            # so the metric is not lost when the handler short-circuits.
            duration = time.perf_counter() - started
            route = self._route_template(request)
            if self._metrics_enabled:
                http_requests_total.labels(method=method, route=route, status="500").inc()
                http_request_duration.labels(method=method, route=route).observe(duration)
            raise

        duration = time.perf_counter() - started
        route = self._route_template(request)
        status = response.status_code

        if self._metrics_enabled:
            http_requests_total.labels(method=method, route=route, status=str(status)).inc()
            http_request_duration.labels(method=method, route=route).observe(duration)

        duration_ms = duration * 1000
        fields = {
            "method": method,
            "route": route,
            "status": status,
            "duration_ms": round(duration_ms, 2),
            # Fingerprint and network, never the address. See core/privacy.py:
            # an IP is personal data, these logs keep thirty days of every
            # request, and the two questions an address actually gets asked in
            # an incident — "same caller?" and "which network?" — are both
            # answerable without it.
            "client": self._fingerprint(request),
            "client_net": self._network(request),
            "user_agent": request.headers.get("user-agent", "")[:200],
        }

        if status >= 500:
            logger.error("request_failed", **fields)
        elif duration_ms > self._slow_ms:
            logger.warning("slow_request", threshold_ms=self._slow_ms, **fields)
        elif status >= 400:
            logger.info("request_rejected", **fields)
        else:
            logger.info("request_completed", **fields)

        return response

    @staticmethod
    def _route_template(request: Request) -> str:
        """The matched route pattern. Falls back to a literal for unmatched
        paths — using the raw 404 path would let a scanner create unbounded
        metric series just by requesting random URLs."""
        route = request.scope.get("route")
        path_format = getattr(route, "path_format", None) or getattr(route, "path", None)
        return str(path_format) if path_format else "unmatched"

    @staticmethod
    def _raw_ip(request: Request) -> str | None:
        """The originating address. Never logged — only fed to the two helpers
        below, which is the entire point of keeping it private."""
        return client_ip_from_headers(
            request.headers.get("x-forwarded-for"),
            request.client.host if request.client else None,
        )

    def _fingerprint(self, request: Request) -> str:
        return client_fingerprint(self._raw_ip(request), salt=self._salt)

    def _network(self, request: Request) -> str:
        return network_prefix(self._raw_ip(request))
