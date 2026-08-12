"""Security response headers.

These are cheap, and each one closes a class of attack that is otherwise
entirely dependent on client behaviour.

* ``X-Content-Type-Options: nosniff`` — stops a browser from deciding that an
  uploaded ``.jpg`` is really HTML and executing it in our origin.
* ``X-Frame-Options: DENY`` — no clickjacking of the booking or payment flow.
* ``Referrer-Policy`` — a booking URL contains an ID; it must not leak to a
  third-party analytics or map tile host via the Referer header.
* ``Strict-Transport-Security`` — deployed environments only. Sending HSTS from
  a local HTTP dev server pins the browser to HTTPS for localhost and breaks
  every developer's machine for a year.
* ``Content-Security-Policy`` — restrictive for the API itself. The SPA has its
  own, served by its own edge; this one protects the ``/docs`` page and any
  HTML an API endpoint might ever return.
* ``Cache-Control: no-store`` on authenticated responses — without it, a shared
  proxy can serve one user's booking list to another.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Settings

_BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
    "X-Permitted-Cross-Domain-Policies": "none",
}

_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

# /docs needs Swagger's CDN assets and its inline bootstrap script.
_DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "frame-ancestors 'none'"
)

_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._is_deployed = settings.app_env.is_deployed

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)

        for key, value in _BASE_HEADERS.items():
            response.headers.setdefault(key, value)

        is_docs = request.url.path.startswith(_DOC_PATHS)
        response.headers.setdefault("Content-Security-Policy", _DOCS_CSP if is_docs else _API_CSP)

        if self._is_deployed:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload"
            )

        # Any request that carried credentials produced a personalised response.
        if "authorization" in request.headers or "cookie" in request.headers:
            response.headers.setdefault("Cache-Control", "no-store, private")

        return response
