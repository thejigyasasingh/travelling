"""Outbound HTTP.

One shared, long-lived ``AsyncClient`` per upstream. Creating a client per
request throws away the connection pool, so every call pays a fresh TCP and
TLS handshake — 100-300 ms of pure latency against a payment gateway, on every
single request.

Every client here is wrapped by a :class:`CircuitBreaker` and carries an
explicit timeout. Those two are not optional decorations; they are what stops a
third-party outage from becoming ours.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Self

import httpx

from app.core.logging import get_logger, request_id_var, trace_id_var
from app.infrastructure.external.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
)

logger = get_logger(__name__)

# Granular, not a single number. Connect failures should surface fast; a
# gateway legitimately needs a few seconds to think about a capture.
DEFAULT_TIMEOUT = httpx.Timeout(connect=3.0, read=10.0, write=5.0, pool=2.0)


class HttpClient:
    """Instrumented wrapper around ``httpx.AsyncClient``."""

    def __init__(
        self,
        *,
        name: str,
        base_url: str = "",
        timeout: httpx.Timeout | None = None,
        headers: dict[str, str] | None = None,
        max_connections: int = 50,
        breaker_config: CircuitBreakerConfig | None = None,
    ) -> None:
        self.name = name
        self.breaker = CircuitBreaker(name, breaker_config)
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout or DEFAULT_TIMEOUT,
            headers={"User-Agent": "roaming-wandering/1.0", **(headers or {})},
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_connections // 2,
                keepalive_expiry=30.0,
            ),
            follow_redirects=False,  # a redirect to an attacker's host is an SSRF primitive
        )

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Correlation headers are attached so a request can be traced into the
        upstream's logs during a joint incident investigation."""
        headers: dict[str, str] = dict(kwargs.pop("headers", {}) or {})
        if (rid := request_id_var.get()) is not None:
            headers.setdefault("X-Request-Id", rid)
        if (tid := trace_id_var.get()) is not None:
            headers.setdefault("X-Trace-Id", tid)

        async def _send() -> httpx.Response:
            response = await self._client.request(method, url, headers=headers, **kwargs)
            # 5xx counts as a dependency failure and feeds the breaker; 4xx does
            # not, because that is our request being wrong.
            if response.status_code >= 500:
                raise ConnectionError(f"{self.name} returned {response.status_code}")
            return response

        response = await self.breaker.call(_send)
        logger.debug(
            "outbound_request",
            upstream=self.name,
            method=method,
            path=url,
            status=response.status_code,
            duration_ms=int(response.elapsed.total_seconds() * 1000),
        )
        return response

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
