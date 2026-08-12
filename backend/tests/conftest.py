"""Shared test fixtures.

Two principles:

**Unit tests touch nothing.** No database, no Redis, no network. They run in
milliseconds, so they run on every save. If a "unit" test needs a container,
it is an integration test and is marked as such.

**Integration tests get real Postgres and real Redis, in throwaway containers.**
Not SQLite, and not mocks. Half of what this system relies on — exclusion
constraints, ``SKIP LOCKED``, partial indexes, JSONB, Lua scripts — does not
exist in SQLite and is invisible to a mock. A test suite that passes against a
substitute proves nothing about the database we actually deploy.

Key generation happens at import time, before any test module imports
``app.core.config`` — settings are validated eagerly, so a missing key would
fail collection rather than a test.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
KEY_DIR = BACKEND_ROOT / "tests" / "fixtures" / "keys"


def _openssl(*args: str) -> None:
    subprocess.run(["openssl", *args], check=True, capture_output=True)  # noqa: S603, S607


def _ensure_test_keys() -> None:
    """Generate the RS256 test keypair if it is absent.

    Runs at import, before ``app.core.config`` is imported anywhere, because
    ``Settings`` reads and validates the key file during construction.
    """
    private = KEY_DIR / "test_jwt_private.pem"
    if private.exists():
        return
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    # openssl is resolved from PATH on purpose — its absolute location differs
    # between macOS, Debian and the CI image, and this is test-fixture setup
    # with no attacker-controlled input.
    _openssl(
        "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private)
    )
    _openssl("rsa", "-pubout", "-in", str(private), "-out", str(KEY_DIR / "test_jwt_public.pem"))
    private.chmod(0o600)


_ensure_test_keys()

# Set before any app import. pytest-env in pyproject.toml covers the common
# case; this makes the suite runnable via a bare `pytest` too.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SECURITY__JWT_PRIVATE_KEY_PATH", str(KEY_DIR / "test_jwt_private.pem"))
os.environ.setdefault("SECURITY__JWT_PUBLIC_KEY_PATH", str(KEY_DIR / "test_jwt_public.pem"))
os.environ.setdefault("LOG_FORMAT", "console")
os.environ.setdefault("CELERY__TASK_ALWAYS_EAGER", "true")
# Argon2 at production cost makes every auth test take ~100ms. The parameters
# themselves are verified by a dedicated test; everywhere else, speed wins.
os.environ.setdefault("SECURITY__ARGON2_MEMORY_KIB", "8192")
os.environ.setdefault("SECURITY__ARGON2_TIME_COST", "1")

if str(BACKEND_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT / "src"))


# ══════════════════════════════════════════════════════════════════════════
# Unit-test fixtures — no I/O
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def frozen_clock():
    """A clock that does not move unless a test moves it.

    Every time-dependent rule — refund windows, token expiry, coupon validity —
    is testable by advancing this rather than by sleeping.
    """
    from app.core.clock import FrozenClock

    return FrozenClock(datetime(2026, 6, 15, 10, 0, tzinfo=UTC))


@pytest.fixture
def settings():
    from app.core.config import get_settings

    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def token_service(settings):
    from app.core.security.tokens import TokenService

    return TokenService(settings.security)


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


# ══════════════════════════════════════════════════════════════════════════
# Integration fixtures — real Postgres and real Redis
#
# Two ways to get them, tried in this order:
#
#   1. **Services already running**, named by `TEST_DATABASE_DSN` and
#      `TEST_REDIS_URL`. This is how CI runs them — GitHub Actions service
#      containers start faster than testcontainers and need no Docker socket —
#      and it is how a developer runs them against a local Postgres.
#   2. **Testcontainers**, which starts throwaway containers.
#
# Falling back rather than requiring one or the other matters more than it
# looks. Before this, the whole integration suite required a Docker socket, so
# on any machine without one it silently collected zero tests — and the API
# surface stayed at 0% coverage while the unit suite reported green.
#
# Session-scoped: starting Postgres takes seconds and doing it per test would
# make the suite unusable. Isolation comes from transaction rollback.
# ══════════════════════════════════════════════════════════════════════════

#: Set by CI, or by a developer pointing at a local database. Anything here is
#: assumed disposable — the suite migrates it and writes to it.
EXTERNAL_DSN = os.environ.get("TEST_DATABASE_DSN")
EXTERNAL_REDIS = os.environ.get("TEST_REDIS_URL")


def _docker_available() -> bool:
    """Whether testcontainers has any chance of working.

    Checked rather than assumed: `importorskip` only proves the library is
    installed, and the failure when the daemon is absent is a 30-second
    connection timeout inside a fixture, repeated per session.
    """
    try:
        import docker

        docker.from_env().ping()
    except Exception:
        return False
    return True


@pytest.fixture(scope="session")
def postgres_dsn() -> Iterator[str]:
    if EXTERNAL_DSN:
        yield EXTERNAL_DSN
        return
    if not _docker_available():
        pytest.skip(
            "no database: set TEST_DATABASE_DSN to a disposable Postgres, "
            "or start Docker for testcontainers"
        )
    from testcontainers.postgres import PostgresContainer

    # PostGIS, not stock Postgres. Property search uses `geography` and
    # `ST_Distance`; against stock Postgres those queries fail to plan and the
    # tests that matter most never run.
    with PostgresContainer("postgis/postgis:17-3.5", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    if EXTERNAL_REDIS:
        yield EXTERNAL_REDIS
        return
    if not _docker_available():
        pytest.skip("no Redis: set TEST_REDIS_URL, or start Docker for testcontainers")
    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7.4-alpine") as rd:
        host = rd.get_container_host_ip()
        port = rd.get_exposed_port(6379)
        yield f"redis://{host}:{port}"


@pytest.fixture(scope="session")
def integration_settings(postgres_dsn: str, redis_url: str) -> Iterator[Any]:
    """Point the settings singleton at whichever services we got.

    **Restores `os.environ` afterwards, and this is not housekeeping.** The
    overrides below include `AUTH__REFRESH_COOKIE_SECURE=false`, which is
    precisely one of the things `Settings` refuses to boot production with. Leak
    it and `tests/unit/test_config.py` fails — but only when the integration
    suite ran first, so the failure looks like a bug in the config validator
    rather than in this fixture. Session-scoped mutation of process state has to
    be undone by the thing that did it.
    """
    from app.core.config import get_settings

    saved = {
        key: os.environ.get(key)
        for key in (
            "DATABASE__DSN",
            "DATABASE__REPLICA_DSN",
            "REDIS__URL",
            "STORAGE__ENDPOINT_URL",
            "STORAGE__PUBLIC_BASE_URL",
            "RATELIMIT__ENABLED",
            "AUTH__REFRESH_COOKIE_SECURE",
        )
    }

    os.environ["DATABASE__DSN"] = postgres_dsn
    os.environ["DATABASE__REPLICA_DSN"] = postgres_dsn
    os.environ["REDIS__URL"] = redis_url

    # No object-storage endpoint. `Settings` reads `.env` from an absolute path
    # next to the source, so a developer's `STORAGE__ENDPOINT_URL=localhost:9000`
    # leaks into every test run — and `Container.startup` calls
    # `ensure_bucket()`, which then retries against a MinIO that is not running
    # until the ASGI lifespan times out. The whole integration suite errors with
    # a bare `CancelledError` that names nothing.
    #
    # Blank makes `ensure_bucket` a no-op, which is what it does in production
    # too. Nothing under test needs a live bucket: uploads are presigned, and
    # presigning is arithmetic over a key and a secret.
    os.environ["STORAGE__ENDPOINT_URL"] = ""
    # Deterministic, so a test asserting on an image URL has something stable
    # to assert against.
    os.environ["STORAGE__PUBLIC_BASE_URL"] = "https://cdn.test.local"

    # Rate limiting **off** for the suite as a whole. Every test signs in, the
    # limiter counts five logins per fifteen minutes per IP, and every test
    # arrives from 127.0.0.1 — so with it on, the sixth test fails and which
    # one that is depends on collection order.
    #
    # It is not left untested: `tests/api/test_rate_limiting.py` builds its own
    # application with limiting enabled and asserts the behaviour directly,
    # which is both more precise and immune to what the rest of the suite did
    # beforehand.
    os.environ["RATELIMIT__ENABLED"] = "false"

    # The refresh cookie is `Secure` in every real environment, and correctly
    # so. The ASGI transport speaks `http://test`, and httpx — behaving exactly
    # as a browser would — refuses to send a Secure cookie over plain HTTP. So
    # every refresh test would fail on the transport rather than on the code.
    #
    # Turned off *here only*. `test_auth_api.py` still asserts that the cookie
    # carries HttpOnly, a scoped Path and SameSite, which are the properties
    # this flag is not standing in for.
    os.environ["AUTH__REFRESH_COOKIE_SECURE"] = "false"

    get_settings.cache_clear()
    try:
        yield get_settings()
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        # The cache holds a Settings built from the overrides above. Anything
        # constructing settings after this point must rebuild from the restored
        # environment, or the restore achieves nothing.
        get_settings.cache_clear()


@pytest.fixture(scope="session")
def migrated_database(integration_settings) -> None:
    """Run Alembic against the throwaway database.

    Migrations, not ``metadata.create_all()``. ``create_all`` builds the schema
    the models describe, which is not necessarily the schema migrations
    produce — and it is the migrations that run in production. Testing against
    ``create_all`` means a broken migration passes CI.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture
async def db_session(integration_settings, migrated_database) -> AsyncIterator[object]:
    """A session wrapped in a transaction that is always rolled back.

    Each test sees a clean database without paying to re-create the schema.
    The rollback is unconditional, so a test that "commits" still leaves
    nothing behind.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.infrastructure.database.session import Database

    database = Database(integration_settings)
    connection = await database.write_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
        await database.dispose()


@pytest.fixture
async def api_client(integration_settings, migrated_database) -> AsyncIterator[object]:
    """HTTP client against the real app, with the real middleware stack.

    ``ASGITransport`` calls the app in-process — no socket, no port, and the
    lifespan runs so the container is built exactly as it is in production.
    """
    import httpx
    from asgi_lifespan import LifespanManager

    from app.interface.api.app import create_app

    app = create_app(integration_settings)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
