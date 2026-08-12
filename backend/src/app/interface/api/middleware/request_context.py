"""Request correlation and timing.

The outermost middleware, so every other layer — including the exception
handlers — runs with correlation IDs already bound.

Two IDs, not one:

* ``request_id`` — this HTTP request. Generated here unless a trusted edge
  supplied one.
* ``trace_id`` — the whole causal chain: request → outbox event → Celery task →
  outbound call. This is what turns "the user says their booking failed" into
  one query.

An inbound ``X-Request-Id`` is accepted but **validated and truncated**. It is
attacker-controlled and lands in logs; a 4 KB header or a newline injected into
a log line is a real attack (log forging, ingestion pipeline crash).
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_var, trace_id_var, user_id_var

_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")

RequestResponseCall = Callable[[Request], Awaitable[Response]]


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseCall) -> Response:
        request_id = self._sanitise(request.headers.get("x-request-id")) or uuid.uuid4().hex
        trace_id = self._sanitise(request.headers.get("x-trace-id")) or request_id

        request_id_var.set(request_id)
        trace_id_var.set(trace_id)
        user_id_var.set(None)  # populated by the auth dependency once resolved

        # Also on request.state so handlers and error responses can read them
        # without touching a contextvar.
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        request.state.started_at = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - request.state.started_at) * 1000
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Trace-Id"] = trace_id
        # Surfaced to clients so a user reporting slowness can be believed with
        # evidence, and so the mobile app can distinguish server time from
        # network time.
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"
        return response

    @staticmethod
    def _sanitise(value: str | None) -> str | None:
        return value if value and _SAFE_ID.match(value) else None
