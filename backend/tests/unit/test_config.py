"""Configuration invariants.

The production-safety tests are the important ones. Each asserts that a
specific unsafe configuration *cannot boot* — a crash loop is a visible,
fixable failure, whereas a production API quietly serving stack traces or
accepting any Host header is not.
"""

from __future__ import annotations

import os
from typing import ClassVar

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.core.config import Environment, RedisSettings, Settings

pytestmark = pytest.mark.unit

BASE = {
    "database": {"dsn": "postgresql+asyncpg://u:p@localhost:5432/db"},
    "redis": {"url": "redis://localhost:6379"},
}

#: The minimum email configuration a deployed environment is allowed to boot
#: with. Spelled out here rather than defaulted, because the whole point of the
#: invariant is that an operator has to make these choices — a deployment that
#: cannot send mail cannot verify an address or reset a password, and so cannot
#: onboard anyone at all.
DEPLOYED_EMAIL = {
    "enabled": True,
    "host": "smtp.example.com",
    "web_base_url": "https://example.com",
}

# Settings reads .env and the process environment. A test asserting "this
# config is rejected" is worthless if a developer's local .env silently
# supplies the missing value — the test would pass for the wrong reason on one
# machine and fail on another.
#: Every nested section on `Settings`, derived from the model rather than
#: listed by hand.
#:
#: It was a hand-written list, and it was missing `AUTH__`. The integration
#: fixture sets `AUTH__REFRESH_COOKIE_SECURE=false` — which is one of the exact
#: things a production config is refused for — so the production-safety tests
#: below failed, but only when the API suite had run first in the same process.
#: The failure pointed at the config validator; the cause was an incomplete
#: list in a test helper. Deriving it means a new section cannot be forgotten.
_SECTION_PREFIXES = tuple(f"{name.upper()}__" for name in Settings.model_fields)

_CONFIG_PREFIXES = ("APP_", "DEBUG", "LOG_", *_SECTION_PREFIXES)


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip every setting from the ambient environment.

    These tests assert on what `Settings` does with a given input, so the input
    has to be only what the test passes — not that plus whatever `.env`, CI, or
    an earlier fixture left lying around.
    """
    for key in list(os.environ):
        if key.upper().startswith(_CONFIG_PREFIXES):
            monkeypatch.delenv(key, raising=False)


def test_the_hermetic_fixture_covers_every_section() -> None:
    """A guard on the guard.

    If a new section is added to `Settings` and this derivation breaks, the
    symptom elsewhere is a test that fails only in certain orders — which is
    hours of debugging aimed at the wrong file.
    """
    assert "AUTH__" in _CONFIG_PREFIXES
    assert len(_SECTION_PREFIXES) >= 10


def build(**overrides: object) -> Settings:
    # _env_file=None: ignore .env entirely, so the inputs are exactly what the
    # test passes.
    return Settings(_env_file=None, **{**BASE, **overrides})  # type: ignore[arg-type]


class TestLocalDefaults:
    def test_local_config_is_permissive(self) -> None:
        settings = build(app_env="local", debug=True, log_format="console")
        assert settings.app_env is Environment.LOCAL

    def test_docs_are_served_outside_production(self) -> None:
        # Staging still enforces the deployment invariants, so this needs a
        # valid deployed config — only the *docs* rule differs from production.
        settings = build(
            app_env="staging",
            log_format="json",
            http={"allowed_hosts": ["staging.example.com"], "cors_origins": []},
            security={"jwt_private_key": "x", "jwt_public_key": "y"},
            email=DEPLOYED_EMAIL,
        )
        assert settings.docs_url == "/docs"


class TestProductionSafety:
    PROD: ClassVar[dict[str, object]] = {
        "app_env": "production",
        "log_format": "json",
        "http": {"allowed_hosts": ["api.example.com"], "cors_origins": ["https://example.com"]},
        "observability": {"sentry_dsn": "https://x@sentry.io/1"},
        "security": {"jwt_private_key": "x", "jwt_public_key": "y"},
        "email": DEPLOYED_EMAIL,
    }

    def test_valid_production_config_boots(self) -> None:
        assert build(**self.PROD).app_env is Environment.PRODUCTION  # type: ignore[arg-type]

    def test_debug_true_refuses_to_boot(self) -> None:
        with pytest.raises(PydanticValidationError, match="DEBUG must be false"):
            build(**{**self.PROD, "debug": True})  # type: ignore[arg-type]

    def test_wildcard_allowed_hosts_refuses_to_boot(self) -> None:
        cfg = {**self.PROD, "http": {"allowed_hosts": ["*"], "cors_origins": []}}
        with pytest.raises(PydanticValidationError, match="ALLOWED_HOSTS"):
            build(**cfg)  # type: ignore[arg-type]

    def test_wildcard_cors_refuses_to_boot(self) -> None:
        # With allow_credentials=True this would be session theft from any origin.
        cfg = {**self.PROD, "http": {"allowed_hosts": ["api.example.com"], "cors_origins": ["*"]}}
        with pytest.raises(PydanticValidationError, match="CORS_ORIGINS"):
            build(**cfg)  # type: ignore[arg-type]

    def test_console_logging_refuses_to_boot(self) -> None:
        with pytest.raises(PydanticValidationError, match="LOG_FORMAT"):
            build(**{**self.PROD, "log_format": "console"})  # type: ignore[arg-type]

    def test_sql_echo_refuses_to_boot(self) -> None:
        # echo_sql writes every bound parameter to the log — including emails,
        # phone numbers and password hashes.
        cfg = {**self.PROD, "database": {**BASE["database"], "echo_sql": True}}
        with pytest.raises(PydanticValidationError, match="ECHO_SQL"):
            build(**cfg)  # type: ignore[arg-type]

    def test_missing_jwt_key_refuses_to_boot(self) -> None:
        with pytest.raises(PydanticValidationError, match="JWT_PRIVATE_KEY"):
            build(**{**self.PROD, "security": {}})  # type: ignore[arg-type]


class TestDatabaseSettings:
    def test_read_dsn_falls_back_to_primary(self) -> None:
        # Never fails closed — a missing replica means slower reads, not none.
        settings = build()
        assert settings.database.read_dsn == settings.database.dsn

    def test_read_dsn_prefers_the_replica(self) -> None:
        settings = build(
            database={
                "dsn": "postgresql+asyncpg://u:p@primary:5432/db",
                "replica_dsn": "postgresql+asyncpg://u:p@replica:5432/db",
            }
        )
        assert "replica" in str(settings.database.read_dsn)

    def test_sync_dsn_swaps_the_driver_for_alembic(self) -> None:
        assert "+psycopg" in build().database.sync_dsn


class TestCelerySettings:
    def test_hard_limit_must_exceed_soft_limit(self) -> None:
        # Otherwise the hard kill fires first and the task never gets its
        # chance to clean up after SoftTimeLimitExceeded.
        with pytest.raises(PydanticValidationError, match="must exceed"):
            build(celery={"task_soft_time_limit_seconds": 300, "task_time_limit_seconds": 200})


class TestRedisSettings:
    def test_logical_databases_are_distinct(self) -> None:
        redis = build().redis
        dbs = {redis.cache_db, redis.lock_db, redis.ratelimit_db, redis.broker_db, redis.pubsub_db}
        assert len(dbs) == 5, "logical DBs must not collide; see redis_client.py"


class TestRedisDatabaseSelection:
    """Composing a per-section Redis URL.

    A database index on `REDIS__URL` used to be appended to rather than
    replaced, producing `redis://host:6379/0/3`. redis-py accepts that, so the
    cache and the rate limiter worked; Celery does not, so `send_task` raised
    `invalid literal for int() with base 10: '0/3'` and **every outbox event
    failed to dispatch** — logged as a warning on a row nobody reads.

    The URL with an index is the common form, not an edge case: it is what
    compose files, hosting dashboards and the redis-py docs all show.
    """

    def test_a_url_without_an_index_gets_one(self) -> None:
        assert RedisSettings(url="redis://localhost:6379").broker_url == "redis://localhost:6379/3"

    def test_a_url_with_an_index_has_it_replaced(self) -> None:
        assert (
            RedisSettings(url="redis://localhost:6379/0").broker_url == "redis://localhost:6379/3"
        )

    def test_a_trailing_slash_is_tolerated(self) -> None:
        assert RedisSettings(url="redis://localhost:6379/").broker_url == "redis://localhost:6379/3"

    def test_credentials_survive(self) -> None:
        """The authority is everything before the path. Dropping a password
        here would fail at connect time against every managed Redis."""
        settings = RedisSettings(url="redis://:secret@redis.internal:6379/2")

        assert settings.broker_url == "redis://:secret@redis.internal:6379/3"

    def test_each_section_gets_its_own_database(self) -> None:
        """Separate indices so `FLUSHDB` on the cache cannot drop the queue."""
        settings = RedisSettings(url="redis://localhost:6379/0")
        indices = {
            settings.dsn_for(settings.cache_db),
            settings.dsn_for(settings.lock_db),
            settings.dsn_for(settings.ratelimit_db),
            settings.broker_url,
            settings.dsn_for(settings.pubsub_db),
        }

        assert len(indices) == 5


class TestEmailInvariants:
    """A deployed environment must be able to send mail.

    Not a style rule. Registration returns `202 unverified` and password reset
    returns `202` whether or not anything is delivered, so an environment with
    no mailer looks healthy from every angle — the API answers, the dashboards
    are green, the logs are clean — while no user can complete a signup. That
    was true of this system until the notification module landed, and the
    invariant is what stops it being true again.
    """

    def test_a_deployed_environment_refuses_to_boot_without_email(self) -> None:
        with pytest.raises(PydanticValidationError, match="EMAIL__ENABLED"):
            build(**{**TestProductionSafety.PROD, "email": {"enabled": False}})

    def test_enabled_without_a_host_is_refused(self) -> None:
        with pytest.raises(PydanticValidationError, match="EMAIL__HOST"):
            build(
                **{
                    **TestProductionSafety.PROD,
                    "email": {**DEPLOYED_EMAIL, "host": "  "},
                }
            )

    def test_a_plaintext_link_host_is_refused(self) -> None:
        """Verification links are emailed, forwarded and clicked on hostile
        networks. Sending someone to `http://` to type a new password is
        handing the token to anyone on the path."""
        with pytest.raises(PydanticValidationError, match="EMAIL__WEB_BASE_URL"):
            build(
                **{
                    **TestProductionSafety.PROD,
                    "email": {**DEPLOYED_EMAIL, "web_base_url": "http://example.com"},
                }
            )

    def test_local_development_may_have_no_mailer(self) -> None:
        """The invariant is for deployed environments only. A contributor
        running the API to look at Swagger should not need an SMTP server."""
        assert build(app_env="local").email.enabled is False

    def test_a_trailing_slash_is_trimmed_from_the_link_host(self) -> None:
        """Templates join with "/", and `https://x.com//verify-email` breaks
        link detection in some clients and every strict router."""
        settings = build(
            app_env="local",
            email={"web_base_url": "https://example.com/"},
        )

        assert settings.email.web_base_url == "https://example.com"
