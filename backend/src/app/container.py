"""Composition root.

**Exactly one place in this codebase constructs infrastructure.** Not a
module-level `redis_client = Redis(...)` here and an `s3 = boto3.client(...)`
there — those are import-time singletons that connect during test collection,
cannot be replaced without monkey-patching, and make startup ordering an
accident of import order.

Why a hand-written container rather than a DI framework:

* The dependency graph of a modular monolith is small and mostly static. A
  library would add magic, a decorator vocabulary and a debugging surface to
  solve a problem that is ~200 lines of explicit wiring.
* Wiring you can read is wiring you can reason about at 3am.
* Everything is typed, so mypy catches a mis-wire; a string-keyed registry
  would not.

Lifecycle: built once in the FastAPI lifespan (and once per Celery worker
process), disposed on shutdown. Nothing here is request-scoped — request-scoped
objects (the session, the Unit of Work, the current actor) are produced by
``interface/api/deps.py`` from these singletons.

Construction is **eager and fails loudly**. A bad DSN or an unreadable key
kills the process at boot rather than producing 500s an hour later under load.
"""

from __future__ import annotations

import asyncio
from typing import Self

from app.core.clock import Clock, SystemClock
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.core.security.password import PasswordHasherService
from app.core.security.tokens import TokenService
from app.infrastructure.cache.cache import RedisCache
from app.infrastructure.cache.idempotency import RedisIdempotencyStore
from app.infrastructure.cache.locks import RedisLockManager
from app.infrastructure.cache.rate_limiter import RedisRateLimiter
from app.infrastructure.cache.redis_client import RedisRegistry
from app.infrastructure.database.session import Database
from app.infrastructure.storage.s3 import S3Storage
from app.modules.ai.infrastructure.llm.anthropic_client import build_language_model
from app.modules.notification.application.ports import EmailSender
from app.modules.notification.infrastructure.smtp import SmtpEmailSender
from app.modules.payment.infrastructure.razorpay_gateway import RazorpayConfig, RazorpayGateway

logger = get_logger(__name__)


async def _noop() -> None:
    """Placeholder awaitable, so shutdown's gather stays one flat call rather
    than growing a conditional list."""


class Container:
    """Holds every long-lived dependency.

    Attributes are assigned in ``__init__`` so a missing dependency is an
    ``AttributeError`` at boot, not a ``KeyError`` deep in a request.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings: Settings = settings or get_settings()

        # ── cross-cutting ────────────────────────────────────────────────
        self.clock: Clock = SystemClock()

        # ── persistence ──────────────────────────────────────────────────
        self.database = Database(self.settings)

        # ── redis-backed services ────────────────────────────────────────
        # One registry, one pool per logical DB. See redis_client.py for why
        # they are not shared.
        self.redis = RedisRegistry(self.settings)
        self.cache = RedisCache(self.redis.cache)
        self.locks = RedisLockManager(self.redis.locks)
        self.rate_limiter = RedisRateLimiter(self.redis.ratelimit)
        self.idempotency = RedisIdempotencyStore(self.redis.cache)

        # ── security ─────────────────────────────────────────────────────
        # Constructed here so an unreadable JWT key fails the deploy rather
        # than the first login.
        self.password_hasher = PasswordHasherService(self.settings.security)
        self.tokens = TokenService(self.settings.security)

        # ── object storage ───────────────────────────────────────────────
        self.storage = S3Storage(self.settings.storage)

        # ── payment gateway ──────────────────────────────────────────────
        # Built here rather than per request: it owns an HTTP connection pool
        # and a circuit breaker, and both are worthless if they are discarded
        # after one call. None when payments are off, so a deployment without
        # Razorpay credentials boots normally and the routes answer 503.
        self.payment_gateway: RazorpayGateway | None = None
        payment = self.settings.payment
        if payment.enabled:
            self.payment_gateway = RazorpayGateway(
                RazorpayConfig(
                    key_id=payment.razorpay_key_id,
                    key_secret=payment.razorpay_key_secret.get_secret_value()
                    if payment.razorpay_key_secret
                    else "",
                    webhook_secret=payment.razorpay_webhook_secret.get_secret_value()
                    if payment.razorpay_webhook_secret
                    else "",
                    auto_capture=payment.auto_capture,
                )
            )

        # ── outbound email ───────────────────────────────────────────────
        # Always constructed, never None. The *suppression* decision belongs to
        # the use case, which records a `suppressed` notification with a reason
        # — a None sender would push that decision into every call site as a
        # branch somebody eventually forgets, and a silently dropped password
        # reset is indistinguishable from a working one until a user complains.
        self.email_sender: EmailSender = SmtpEmailSender(self.settings.email)

        # ── language model ───────────────────────────────────────────────
        # One instance, because it owns a connection pool and a circuit
        # breaker and both are worthless if discarded after a call. Returns a
        # null object rather than None when AI is off, so every call site is
        # `if model.available` instead of a None check somebody forgets.
        self.language_model = build_language_model(self.settings.ai)

        # Module containers are attached here as they land — e.g.
        #   self.auth = AuthModule(self)
        # each exposing its use cases. The module owns its own wiring; this
        # class stays a list of infrastructure, not a list of every use case
        # in the system.

        logger.info(
            "container_built",
            env=self.settings.app_env.value,
            version=self.settings.app_version,
        )

    # ── lifecycle ─────────────────────────────────────────────────────────

    async def startup(self) -> Self:
        """Verify every hard dependency before accepting traffic.

        A pod that boots without Postgres and starts serving 500s passes its
        liveness probe and is happily added to the load balancer. Failing here
        means the rollout stalls with a clear error instead.
        """
        await self.database.ping()
        await self.redis.ping()
        await self.storage.ensure_bucket()  # no-op outside local/MinIO
        logger.info("container_started")
        return self

    async def shutdown(self) -> None:
        """Release everything. Order matters: stop using connections before
        closing the pools they came from."""
        await asyncio.gather(
            self.database.dispose(),
            self.redis.close(),
            self.payment_gateway.aclose() if self.payment_gateway else _noop(),
            return_exceptions=True,  # one failing close must not skip the others
        )
        logger.info("container_stopped")

    # ── health ────────────────────────────────────────────────────────────

    async def check_dependencies(self) -> dict[str, dict[str, object]]:
        """Used by the readiness probe. Every check is individually timed and
        individually failable, so the probe can report *which* dependency is
        down instead of a bare "not ready"."""

        async def _timed(name: str, coro: object) -> tuple[str, dict[str, object]]:
            loop = asyncio.get_running_loop()
            started = loop.time()
            try:
                async with asyncio.timeout(2.0):
                    await coro  # type: ignore[misc]
            except Exception as exc:
                return name, {
                    "status": "down",
                    "error": type(exc).__name__,
                    "latency_ms": int((loop.time() - started) * 1000),
                }
            return name, {"status": "up", "latency_ms": int((loop.time() - started) * 1000)}

        results = await asyncio.gather(
            _timed("postgres", self.database.ping()),
            _timed("postgres_replica", self.database.ping(replica=True)),
            _timed("redis", self.redis.ping()),
        )
        return dict(results)


# ══════════════════════════════════════════════════════════════════════════
# Process-wide accessor
#
# The API gets its container from ``app.state`` (see deps.py) and never touches
# this. It exists for entry points that have no request scope — Celery tasks,
# CLI commands — where a per-process singleton is the correct lifetime.
# ══════════════════════════════════════════════════════════════════════════

_container: Container | None = None
_lock = asyncio.Lock()


async def get_container() -> Container:
    global _container
    if _container is None:
        async with _lock:
            if _container is None:  # re-check: two tasks can await the same lock
                configure_logging(get_settings())
                _container = await Container().startup()
    return _container


async def reset_container() -> None:
    """Test hook. Disposes and clears the singleton so the next call rebuilds
    it against a fresh set of containers."""
    global _container
    if _container is not None:
        await _container.shutdown()
    _container = None
