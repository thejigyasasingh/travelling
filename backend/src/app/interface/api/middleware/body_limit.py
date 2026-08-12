"""Request body size limit.

Without this, ``POST /reviews`` with a 2 GB body is a one-line denial of
service: FastAPI buffers the body before a handler ever runs, so validation
cannot save you — the memory is already gone.

Two checks, because either alone is insufficient:

1. ``Content-Length`` — rejected before a single byte of body is read. Cheap,
   and covers every well-behaved client.
2. Streaming count — a chunked request has no ``Content-Length``, so the actual
   bytes are counted as they arrive and the connection is cut the moment the
   cap is crossed.

Uploads are exempt because they do not come here at all: media goes directly
to S3 via a presigned POST whose ``content-length-range`` condition S3 itself
enforces. See ``infrastructure/storage/s3.py``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_413_CONTENT_TOO_LARGE

from app.core.errors import ErrorCode
from app.core.logging import get_logger

logger = get_logger(__name__)

_BODYLESS_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "DELETE"})


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, *, max_bytes: int, max_json_bytes: int) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_bytes = max_bytes
        # JSON is capped much lower than multipart. A megabyte of JSON is
        # already an unreasonable request body, and parsing deeply nested JSON
        # is CPU-expensive in a way that raw bytes are not.
        self._max_json_bytes = max_json_bytes

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in _BODYLESS_METHODS:
            return await call_next(request)

        limit = self._limit_for(request)

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > limit:
                    return self._too_large(request, int(content_length), limit)
            except ValueError:
                pass  # malformed header; the streaming guard below still applies

        request = self._wrap_stream(request, limit)
        return await call_next(request)

    def _limit_for(self, request: Request) -> int:
        content_type = request.headers.get("content-type", "")
        is_json = content_type.startswith("application/json")
        return self._max_json_bytes if is_json else self._max_bytes

    def _wrap_stream(self, request: Request, limit: int) -> Request:
        """Replace the ASGI receive callable with a counting one.

        Done at the ASGI level rather than by reading ``await request.body()``,
        because reading the body here would consume it before the route handler
        gets a chance.
        """
        original_receive = request.receive
        seen = 0

        async def counting_receive() -> dict[str, object]:
            nonlocal seen
            message = await original_receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise BodyTooLargeError(seen, limit)
            return message  # type: ignore[return-value]

        return Request(request.scope, counting_receive)

    @staticmethod
    def _too_large(request: Request, size: int, limit: int) -> JSONResponse:
        logger.info("request_body_too_large", path=request.url.path, size=size, limit=limit)
        return JSONResponse(
            status_code=HTTP_413_CONTENT_TOO_LARGE,
            content={
                "error": {
                    "code": ErrorCode.PAYLOAD_TOO_LARGE,
                    "message": "Request body is too large.",
                    "details": {"max_bytes": limit},
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )


class BodyTooLargeError(Exception):
    """Raised from inside the receive callable; converted to a 413 by the
    global exception handler."""

    def __init__(self, size: int, limit: int) -> None:
        self.size = size
        self.limit = limit
        super().__init__(f"Body of {size} bytes exceeds the {limit}-byte limit")
