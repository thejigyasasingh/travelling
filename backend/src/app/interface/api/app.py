"""FastAPI application factory.

A factory, not a module-level ``app = FastAPI()``. The difference matters:
a module-level app is constructed at import time, which means importing
anything from this package opens database pools — including during test
collection. ``create_app(settings)`` lets a test build an app against
throwaway containers, and lets the same code serve local, staging and
production without an ``if``.

**Middleware order is the load-bearing detail of this file.**

Starlette wraps each ``add_middleware`` call *around* the previous one, so the
**last added is the outermost** and sees the request first. The intended order,
outermost inward:

    1. RequestContext   — correlation IDs exist for everything below
    2. SecurityHeaders  — must decorate every response, including 500s and
                          rate-limit rejections generated below it
    3. AccessLog        — times and counts everything below, including errors
    4. CORS             — must answer OPTIONS preflights *before* rate limiting;
                          a throttled preflight breaks the whole browser app
    5. BodySizeLimit    — reject oversized bodies before anything reads them
    6. RateLimit        — innermost, so a rejected request has still been
                          logged and still carries correlation headers
    7. (routes)

Getting this wrong is subtle and expensive: put CORS inside the rate limiter
and browsers see opaque failures; put security headers innermost and error
responses ship without them.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.container import Container
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.interface.api.exception_handlers import register_exception_handlers
from app.interface.api.middleware.access_log import AccessLogMiddleware
from app.interface.api.middleware.body_limit import BodySizeLimitMiddleware
from app.interface.api.middleware.rate_limit import RateLimitMiddleware
from app.interface.api.middleware.request_context import RequestContextMiddleware
from app.interface.api.middleware.security_headers import SecurityHeadersMiddleware
from app.interface.api.routes import health, meta
from app.interface.api.v1.router import api_router

logger = get_logger(__name__)

DESCRIPTION = """
Roaming & Wandering — travel booking platform API.

**Errors** always have the shape `{"error": {code, message, details, request_id}}`.
Switch on `code`; never parse `message`.

**Pagination** is cursor-based. Pass the `meta.next_cursor` of one response as
the `cursor` of the next. Cursors are opaque — do not construct them.

**Idempotency**: every state-changing POST accepts an `Idempotency-Key` header,
and booking and payment endpoints require one. Retrying with the same key
returns the original response instead of acting twice.
"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=DESCRIPTION,
        docs_url=settings.docs_url,  # None in production — see config.py
        redoc_url="/redoc" if settings.docs_url else None,
        openapi_url="/openapi.json" if settings.docs_url else None,
        root_path=settings.http.root_path,
        lifespan=_lifespan,
        # 422 is what FastAPI actually returns for validation failures; the
        # default OpenAPI schema says 200 only, which misleads client codegen.
        responses={422: {"description": "Validation error"}},
    )
    app.state.settings = settings

    _register_middleware(app, settings)
    register_exception_handlers(app, settings)

    app.include_router(health.router)
    app.include_router(meta.router)
    app.include_router(api_router)

    logger.info("app_created", env=settings.app_env.value, docs=bool(settings.docs_url))
    return app


# ══════════════════════════════════════════════════════════════════════════
# Lifespan
# ══════════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Own the container's lifetime.

    Everything expensive is built *here*, not at import. Startup verifies every
    hard dependency before the first request is accepted — a pod that cannot
    reach Postgres must fail its rollout, not join the load balancer and serve
    500s.

    Shutdown drains pools so in-flight requests finish. Without it, a rolling
    deploy severs live connections and users see errors during every release.
    """
    settings: Settings = app.state.settings

    container = Container(settings)
    try:
        await container.startup()
    except Exception:
        logger.exception("startup_failed")
        await container.shutdown()
        raise  # non-zero exit; the orchestrator halts the rollout

    # Middleware and dependencies both read the container from here, so it must
    # be set before the first request is accepted.
    app.state.container = container

    logger.info("application_ready", version=settings.app_version)
    try:
        yield
    finally:
        await container.shutdown()
        logger.info("application_stopped")


# ══════════════════════════════════════════════════════════════════════════
# Middleware
# ══════════════════════════════════════════════════════════════════════════


def _register_middleware(app: FastAPI, settings: Settings) -> None:
    """Added innermost-first; see the module docstring for the resulting order."""

    # ── 6. innermost: rate limiting ───────────────────────────────────────
    # The limiter itself is resolved per request from app.state.container,
    # which does not exist until the lifespan runs.
    app.add_middleware(RateLimitMiddleware, settings=settings)

    # ── 5. body size ──────────────────────────────────────────────────────
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=settings.http.max_request_bytes,
        max_json_bytes=settings.http.max_json_bytes,
    )

    # ── 4. CORS ───────────────────────────────────────────────────────────
    # Explicit origins, never "*". `allow_credentials=True` with a wildcard is
    # rejected by browsers anyway, and would be a session-theft vector if it
    # were not.
    if settings.http.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.http.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "Idempotency-Key",
                "X-Request-Id",
                "Accept-Language",
            ],
            expose_headers=[
                "X-Request-Id",
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "Retry-After",
            ],
            max_age=600,  # cache preflights; without it every POST costs two round trips
        )

    # ── compression ───────────────────────────────────────────────────────
    # Search responses are large and highly repetitive JSON. 500 bytes is the
    # floor because compressing below roughly one MTU costs CPU and saves
    # nothing.
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # ── 3. access log + metrics ───────────────────────────────────────────
    app.add_middleware(AccessLogMiddleware, settings=settings)

    # ── Host header validation ────────────────────────────────────────────
    # Blocks Host-header poisoning, where an attacker-controlled Host ends up
    # in a password-reset link that then points at their server.
    if settings.app_env.is_deployed:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.http.allowed_hosts)

    # ── 2. security headers ───────────────────────────────────────────────
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)

    # ── 1. outermost: correlation ─────────────────────────────────────────
    app.add_middleware(RequestContextMiddleware)
