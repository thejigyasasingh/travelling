"""Application configuration.

Design notes
------------
* **Fail fast at boot, never at request time.** Every setting is validated when
  the process starts. A missing JWT key or a malformed DSN kills the container
  before it can accept traffic and serve 500s for an hour.
* **Nested models, not a flat namespace.** ``settings.database.pool_size`` says
  where the value belongs; ``DATABASE_POOL_SIZE`` on a 60-field god-object does
  not. Env vars map via the ``__`` delimiter.
* **Production self-defends.** ``DEBUG=true`` in production is not a warning,
  it is a boot failure — see :meth:`Settings._enforce_production_invariants`.
* **Cached singleton.** ``get_settings()`` is ``lru_cache``d so config is read
  once. Tests clear the cache rather than mutating a global.
"""

from __future__ import annotations

import sys
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import (
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_deployed(self) -> bool:
        return self in (Environment.STAGING, Environment.PRODUCTION)


# ══════════════════════════════════════════════════════════════════════════
# Sections
# ══════════════════════════════════════════════════════════════════════════


def _blank_to_none(value: object) -> object:
    """Treat an empty string as "not configured".

    An unset variable in a Docker Compose file arrives as `""`, not as an
    absent key — `FOO: ${FOO:-}` is the standard way to write an optional
    setting and it always delivers a string. Every `X | None` field that an
    operator might reasonably leave blank needs this, and each one that lacks
    it is a container that will not start:

    * `STORAGE__ENDPOINT_URL` blank means "real AWS S3", and boto3 rejects an
      empty endpoint with `ValueError: Invalid endpoint:` at construction.
    * `DATABASE__REPLICA_DSN` blank means "no replica", and `PostgresDsn`
      rejects it during validation.

    Both fail at boot, on the deployment least likely to have been rehearsed.
    """
    if isinstance(value, str) and not value.strip():
        return None
    return value


class HTTPSettings(BaseSettings):
    host: str = "0.0.0.0"  # noqa: S104 — binds inside a container, not on a host NIC
    port: int = Field(default=8000, ge=1, le=65535)
    root_path: str = ""
    #: Which `Host` headers to answer. The `["*"]` default is for local
    #: development only — in production this must name the real hosts. A
    #: wildcard lets an attacker send `Host: evil.example`, which the
    #: application then uses to build password-reset links.
    #: `NoDecode` stops pydantic-settings JSON-decoding these before the
    #: validator below runs. Without it a comma-separated value raises inside
    #: the environment source — before any validator, with a message naming
    #: only the section — and the process exits. Which is what happened the
    #: first time this compose file met the real Settings class.
    allowed_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)
    max_request_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    max_json_bytes: int = Field(default=1024 * 1024, ge=1024)

    @field_validator("allowed_hosts", "cors_origins", mode="before")
    @classmethod
    def _accept_comma_separated(cls, value: object) -> object:
        """Take `a,b` as well as `["a","b"]`.

        pydantic-settings parses a `list[str]` field from the environment as
        JSON, so `CORS_ORIGINS=https://a,https://b` — the form everyone
        actually writes, and the form every deployment guide shows — raises a
        parse error and the process exits before it logs anything useful.

        The failure is worth avoiding rather than documenting: it happens at
        boot on the first deploy to a new environment, with a message that
        names the field and not the reason.
        """
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            # Still JSON if it looks like JSON — the existing .env files use
            # that form and must keep working. Parsed here rather than handed
            # back as a string: the environment source parses complex types
            # before this validator runs, but a value supplied directly as a
            # keyword argument does not, and returning the raw string then
            # fails with a type error rather than a parse error.
            if text.startswith("["):
                import json

                try:
                    return json.loads(text)
                except ValueError:
                    return [
                        part.strip(" []\"'") for part in text.split(",") if part.strip(" []\"'")
                    ]
            return [part.strip() for part in text.split(",") if part.strip()]
        return value


class DatabaseSettings(BaseSettings):
    """Postgres. Note the deliberate write/read split.

    ``dsn`` is the primary and is the ONLY target for writes. ``replica_dsn``
    serves search and reporting. A booking that read availability from a
    replica would corrupt inventory via replication lag, so the two engines
    are separate objects rather than one engine with a routing flag — the
    choice is then explicit at every call site instead of buried in config.
    """

    dsn: PostgresDsn
    replica_dsn: PostgresDsn | None = None

    #: Blank means "no replica"; `read_dsn` then falls back to the primary.
    _replica_blank = field_validator("replica_dsn", mode="before")(_blank_to_none)

    pool_size: int = Field(default=10, ge=1, le=100)
    max_overflow: int = Field(default=5, ge=0, le=100)
    pool_timeout_seconds: float = Field(default=10.0, gt=0)
    pool_recycle_seconds: int = Field(default=1800, gt=0)
    pool_pre_ping: bool = True

    statement_timeout_ms: int = Field(default=15_000, gt=0)
    lock_timeout_ms: int = Field(default=2_000, gt=0)
    echo_sql: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def read_dsn(self) -> PostgresDsn:
        """Replica if configured, else the primary. Never fails closed."""
        return self.replica_dsn or self.dsn

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_dsn(self) -> str:
        """psycopg DSN for Alembic, which has no async story worth having."""
        return str(self.dsn).replace("+asyncpg", "+psycopg")


class RedisSettings(BaseSettings):
    url: RedisDsn
    cache_db: int = Field(default=0, ge=0, le=15)
    lock_db: int = Field(default=1, ge=0, le=15)
    ratelimit_db: int = Field(default=2, ge=0, le=15)
    broker_db: int = Field(default=3, ge=0, le=15)
    pubsub_db: int = Field(default=4, ge=0, le=15)
    max_connections: int = Field(default=50, ge=1)
    socket_timeout_seconds: float = Field(default=2.0, gt=0)

    def dsn_for(self, db: int) -> str:
        """The base URL with this section's database index.

        **Any database index already on `REDIS__URL` is replaced, not appended
        to.** `redis://host:6379/0` is how almost everyone writes a Redis URL —
        it is what `docker-compose` templates, hosting dashboards and the
        redis-py docs all show — and naively appending produced
        `redis://host:6379/0/3`. redis-py tolerates that; Celery does not, and
        fails with `invalid literal for int() with base 10: '0/3'` from inside
        `send_task`.

        Which meant: the cache worked, the rate limiter worked, the app booted
        and served traffic, and **every outbox event failed to dispatch** —
        recorded as a warning on a row nobody was watching. The one component
        that broke was the one whose failure is silent.
        """
        base = str(self.url).rstrip("/")
        scheme, _, rest = base.partition("://")
        authority, slash, _existing_db = rest.partition("/")
        del slash, _existing_db
        return f"{scheme}://{authority}/{db}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def broker_url(self) -> str:
        return self.dsn_for(self.broker_db)


class CelerySettings(BaseSettings):
    task_always_eager: bool = False
    worker_concurrency: int = Field(default=4, ge=1)
    task_soft_time_limit_seconds: int = Field(default=300, gt=0)
    task_time_limit_seconds: int = Field(default=360, gt=0)
    task_max_retries: int = Field(default=5, ge=0)

    @model_validator(mode="after")
    def _hard_limit_exceeds_soft(self) -> Self:
        if self.task_time_limit_seconds <= self.task_soft_time_limit_seconds:
            msg = "task_time_limit_seconds must exceed task_soft_time_limit_seconds"
            raise ValueError(msg)
        return self


class SecuritySettings(BaseSettings):
    jwt_private_key_path: Path | None = None
    jwt_public_key_path: Path | None = None
    jwt_private_key: SecretStr | None = None  # injected directly in production
    jwt_public_key: SecretStr | None = None
    jwt_key_id: str = "dev-1"
    jwt_algorithm: Literal["RS256"] = "RS256"
    jwt_issuer: str = "roaming-wandering"
    jwt_audience: str = "roaming-wandering-api"

    access_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    refresh_token_ttl_seconds: int = Field(default=30 * 24 * 3600, ge=3600)
    refresh_rotation_grace_seconds: int = Field(default=10, ge=0, le=120)

    argon2_time_cost: int = Field(default=3, ge=1)
    argon2_memory_kib: int = Field(default=65536, ge=8192)
    argon2_parallelism: int = Field(default=4, ge=1)

    @model_validator(mode="after")
    def _resolve_keys(self) -> Self:
        """Accept either a path (local) or the PEM itself (production secrets).

        Reading the key here means a missing or unreadable key is a boot
        failure. The alternative — lazy-loading on first token issue — turns a
        deploy-time misconfiguration into a 500 on someone's login.
        """
        if self.jwt_private_key is None and self.jwt_private_key_path is not None:
            path = self.jwt_private_key_path
            if not path.is_absolute():
                path = BASE_DIR / path
            if not path.is_file():
                msg = f"JWT private key not found at {path}"
                raise ValueError(msg)
            self.jwt_private_key = SecretStr(path.read_text())

        if self.jwt_public_key is None and self.jwt_public_key_path is not None:
            path = self.jwt_public_key_path
            if not path.is_absolute():
                path = BASE_DIR / path
            if not path.is_file():
                msg = f"JWT public key not found at {path}"
                raise ValueError(msg)
            self.jwt_public_key = SecretStr(path.read_text())

        return self


class AuthSettings(BaseSettings):
    """Sign-in methods and their provider configuration."""

    #: Every OAuth client id that may appear as the token's audience. A list
    #: because web, Android and iOS each have their own, and all three are
    #: legitimate — see infrastructure/google_oauth.py for why checking the
    #: audience at all is the load-bearing part.
    google_client_ids: list[str] = Field(default_factory=list)
    google_enabled: bool = False

    otp_enabled: bool = True
    #: Returns the OTP in the API response so local and staging can complete
    #: the flow with no SMS gateway. Forced off in deployed environments by
    #: `_enforce_production_invariants`.
    otp_expose_debug_code: bool = False

    #: Refresh token in a Set-Cookie as well as the body. Browsers get an
    #: HttpOnly cookie that JavaScript — and therefore XSS — cannot read;
    #: mobile clients ignore it and use the body. See interface/router.py.
    refresh_cookie_enabled: bool = True
    refresh_cookie_name: str = "rw_refresh"
    refresh_cookie_domain: str | None = None
    refresh_cookie_secure: bool = True
    refresh_cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    @model_validator(mode="after")
    def _google_needs_client_ids(self) -> Self:
        if self.google_enabled and not self.google_client_ids:
            msg = "AUTH__GOOGLE_CLIENT_IDS is required when Google sign-in is enabled"
            raise ValueError(msg)
        return self


class PaymentSettings(BaseSettings):
    """Razorpay credentials and behaviour.

    Three separate secrets, and they are genuinely separate:
    ``key_id`` is public (the browser needs it to open checkout), ``key_secret``
    signs the checkout callback and authenticates API calls, and
    ``webhook_secret`` signs webhooks. A leaked webhook secret must not let
    anyone call the API, which is why it is not the same value.
    """

    enabled: bool = False
    gateway: Literal["razorpay"] = "razorpay"
    razorpay_key_id: str = ""
    razorpay_key_secret: SecretStr | None = None
    razorpay_webhook_secret: SecretStr | None = None

    #: Razorpay captures automatically on authorisation. On by default: a
    #: separate capture step is another chance to fail, and an uncaptured
    #: authorisation reverses after a few days leaving a confirmed booking
    #: nobody was paid for.
    auto_capture: bool = True
    #: `optimum` costs a fee and lands in minutes; `normal` is free and takes
    #: 5-7 working days. Default free; the platform pays for speed only when
    #: it caused the cancellation.
    default_refund_speed: Literal["normal", "optimum"] = "normal"
    max_attempts_per_booking: int = Field(default=5, ge=1, le=20)
    #: How long a webhook payload is retained. Long enough to replay a
    #: mishandled delivery; not longer, because payloads contain guest contact
    #: details.
    webhook_retention_days: int = Field(default=30, ge=1, le=365)

    @model_validator(mode="after")
    def _credentials_present_when_enabled(self) -> Self:
        if not self.enabled:
            return self
        missing = [
            name
            for name, value in (
                ("PAYMENT__RAZORPAY_KEY_ID", self.razorpay_key_id),
                ("PAYMENT__RAZORPAY_KEY_SECRET", self.razorpay_key_secret),
                ("PAYMENT__RAZORPAY_WEBHOOK_SECRET", self.razorpay_webhook_secret),
            )
            if not value
        ]
        if missing:
            msg = f"Payments are enabled but these are unset: {', '.join(missing)}"
            raise ValueError(msg)
        return self


class RateLimitSettings(BaseSettings):
    enabled: bool = True
    anon_per_minute: int = Field(default=100, ge=1)
    user_per_minute: int = Field(default=300, ge=1)
    search_anon_per_minute: int = Field(default=60, ge=1)
    login_per_15min: int = Field(default=5, ge=1)
    otp_per_hour: int = Field(default=3, ge=1)
    booking_per_hour: int = Field(default=10, ge=1)
    # Redis down => allow traffic. Rate limiting is protective, not correctness:
    # failing closed converts a cache blip into a total outage. Auth endpoints
    # override this and fail closed — see middleware/rate_limit.py.
    fail_open: bool = True


class ObservabilitySettings(BaseSettings):
    sentry_dsn: SecretStr | None = None
    #: Salt for the client fingerprint in access logs and rate-limit buckets.
    #:
    #: Optional, and worth setting. A bare SHA-256 of an IPv4 address is
    #: reversible by brute force — the space is 2^32 — so an unsalted digest
    #: pseudonymises rather than anonymises. A salt also stops fingerprints
    #: being comparable across deployments. Rotating it re-buckets live rate
    #: limits once, which is harmless.
    ip_hash_salt: SecretStr | None = None
    _salt_blank = field_validator("ip_hash_salt", mode="before")(_blank_to_none)
    sentry_traces_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    otel_endpoint: str | None = None
    metrics_enabled: bool = True
    slow_request_ms: int = Field(default=1000, gt=0)


class AISettings(BaseSettings):
    """The language model, and the limits on what it may cost.

    Off by default, and everything that uses it degrades rather than fails —
    recommendations fall back to the same ranking without the written
    explanation, chat falls back to search, sentiment simply does not appear.
    A model outage must never be a booking outage.

    The budgets are not advisory. Token spend is the one dependency here that
    bills per call and can be driven by anyone with a keyboard, so every
    entry point is metered per user and the daily cap is enforced before the
    request is made rather than reconciled afterwards.
    """

    enabled: bool = False
    api_key: SecretStr | None = None
    base_url: str = "https://api.anthropic.com"
    api_version: str = "2023-06-01"

    #: The workhorse: chat, itineraries, the prose on a recommendation.
    model: str = "claude-sonnet-5"
    #: Classification and tagging — high volume, narrow output, no judgement
    #: call worth paying Sonnet for.
    fast_model: str = "claude-haiku-4-5-20251001"

    #: Ceilings, not targets. A model that ignores its instructions and writes
    #: an essay costs the same as one that is being attacked.
    max_output_tokens: int = Field(default=2048, ge=64, le=8192)
    request_timeout_seconds: float = Field(default=45.0, gt=0, le=300)

    #: Per user, per day. A generated itinerary is the expensive one; chat is
    #: metered per message and shares the same daily pool.
    itineraries_per_user_per_day: int = Field(default=10, ge=0)
    chat_messages_per_user_per_hour: int = Field(default=40, ge=0)

    #: Nothing sent to the model may exceed this. Long free text is the cheap
    #: half of a prompt-injection attempt and there is no legitimate 50KB
    #: chat message.
    max_input_chars: int = Field(default=8_000, ge=200)

    #: How long a generated itinerary stays reusable. Itineraries are keyed by
    #: what was asked for, not by who asked, so two guests asking the same
    #: question of the same city pay for one generation.
    itinerary_cache_days: int = Field(default=14, ge=0, le=90)

    @model_validator(mode="after")
    def _key_present_when_enabled(self) -> Self:
        if self.enabled and not self.api_key:
            msg = "AI__ENABLED is true but AI__API_KEY is unset"
            raise ValueError(msg)
        return self


class StorageSettings(BaseSettings):
    endpoint_url: str | None = None  # None => real AWS S3

    #: Blank means real AWS S3. Without this, `STORAGE__ENDPOINT_URL:
    #: ${S3_ENDPOINT_URL:-}` — which is how the production compose writes it,
    #: and what the example file tells operators to leave empty for AWS —
    #: reaches boto3 as `""` and raises `Invalid endpoint:` before the
    #: application logs anything.
    _endpoint_blank = field_validator("endpoint_url", mode="before")(_blank_to_none)
    access_key: SecretStr | None = None
    secret_key: SecretStr | None = None
    bucket: str = "rw-media-local"
    region: str = "ap-south-1"
    presign_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    #: Where property photographs are served from — a CDN in production, the
    #: MinIO console locally. Public, deliberately: listing images are on a
    #: public page, and presigning twenty of them per wishlist render buys
    #: nothing but latency and an expiry that breaks a bookmarked page.
    #: Empty means "no public URL", and callers render a placeholder.
    public_base_url: str = ""


class EmailSettings(BaseSettings):
    """Outbound email.

    **`enabled` defaults to False, and that is not a safety default — it is an
    honest one.** With no SMTP host configured there is nothing to connect to,
    and a system that queues verification mails into a void is worse than one
    that says it cannot send them: the first looks healthy on every dashboard
    while no user can complete a signup. Off means notifications are recorded
    as `suppressed` with a reason, which is visible.

    Production refuses to boot without a host — see the deployment invariants
    at the bottom of this file. There is no configuration of a live environment
    in which silently dropping password resets is acceptable.
    """

    enabled: bool = False

    host: str = "localhost"
    port: int = Field(default=1025, ge=1, le=65535)
    username: str | None = None
    password: SecretStr | None = None

    #: STARTTLS on an established plaintext connection (587), versus TLS from
    #: the first byte (465). Providers differ and getting it wrong fails at
    #: connect time with an error that does not name the cause, so both are
    #: explicit rather than inferred from the port.
    start_tls: bool = True
    tls: bool = False

    #: A blank username means an unauthenticated relay — normal for Mailpit and
    #: for a sidecar submission agent, never for a public provider.
    _blank_user = field_validator("username", mode="before")(_blank_to_none)

    from_address: str = "no-reply@roamingwandering.com"
    from_name: str = "Roaming & Wandering"
    reply_to: str | None = None

    #: Bounded so a hung SMTP server cannot pin a worker indefinitely. Sending
    #: happens off the request path, but a worker stuck here is a worker not
    #: draining the queue.
    timeout_seconds: float = Field(default=10.0, gt=0, le=120)

    #: Where the links in a message point. This is the *customer site*, not the
    #: API: a verification link is opened by a person in a browser, and sending
    #: them to an API host shows them JSON.
    web_base_url: str = "http://localhost:5173"

    @field_validator("web_base_url")
    @classmethod
    def _no_trailing_slash(cls, value: str) -> str:
        # Templates join with "/", and "…//verify" breaks some mail clients'
        # link detection and every strict router.
        return value.rstrip("/")


# ══════════════════════════════════════════════════════════════════════════
# Root
# ══════════════════════════════════════════════════════════════════════════


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
        validate_default=True,
    )

    app_env: Environment = Environment.LOCAL
    app_name: str = "Roaming & Wandering API"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: Annotated[str, Field(pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")] = "INFO"
    log_format: Literal["console", "json"] = "json"

    http: HTTPSettings = Field(default_factory=HTTPSettings)
    database: DatabaseSettings
    redis: RedisSettings
    celery: CelerySettings = Field(default_factory=CelerySettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    payment: PaymentSettings = Field(default_factory=PaymentSettings)
    ratelimit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    ai: AISettings = Field(default_factory=AISettings)

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _enforce_production_invariants(self) -> Self:
        """Refuse to boot in a knowingly unsafe production configuration.

        Each of these has caused a real incident somewhere. A crash loop is a
        visible, fixable failure; a production API serving stack traces or
        accepting any Host header is a silent one.
        """
        if not self.app_env.is_deployed:
            return self

        problems: list[str] = []

        if self.debug:
            problems.append("DEBUG must be false in staging/production")
        if self.log_format != "json":
            problems.append("LOG_FORMAT must be 'json' in staging/production")
        if "*" in self.http.allowed_hosts:
            problems.append("HTTP__ALLOWED_HOSTS must not contain '*'")
        if "*" in self.http.cors_origins:
            problems.append("HTTP__CORS_ORIGINS must not contain '*' (credentials are sent)")
        if self.database.echo_sql:
            problems.append("DATABASE__ECHO_SQL must be false (leaks PII into logs)")
        if self.security.jwt_private_key is None:
            problems.append("SECURITY__JWT_PRIVATE_KEY is required")
        if self.auth.otp_expose_debug_code:
            problems.append("AUTH__OTP_EXPOSE_DEBUG_CODE must be false (returns OTPs to callers)")
        if not self.auth.refresh_cookie_secure:
            problems.append(
                "AUTH__REFRESH_COOKIE_SECURE must be true (cookie sent over plain HTTP)"
            )
        if self.app_env is Environment.PRODUCTION and self.observability.sentry_dsn is None:
            problems.append("OBSERVABILITY__SENTRY_DSN is required in production")
        # A deployed environment that cannot send mail cannot verify an email
        # address or reset a password — which means it cannot onboard a single
        # user, while every dashboard stays green. This invariant exists
        # because that was true of this system for its entire history before
        # anyone tried to sign up.
        if not self.email.enabled:
            problems.append(
                "EMAIL__ENABLED must be true (without it, no user can verify an "
                "address or reset a password)"
            )
        if self.email.enabled and not self.email.host.strip():
            problems.append("EMAIL__HOST is required when email is enabled")
        if self.email.web_base_url.startswith("http://"):
            problems.append("EMAIL__WEB_BASE_URL must be https (verification links are emailed)")

        if problems:
            msg = "Unsafe configuration for {}:\n  - {}".format(
                self.app_env.value, "\n  - ".join(problems)
            )
            raise ValueError(msg)
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def docs_url(self) -> str | None:
        """OpenAPI docs are dev/staging only. In production the schema is
        published to the internal developer portal instead — a public schema
        is a free endpoint map for anyone probing the API."""
        return None if self.app_env is Environment.PRODUCTION else "/docs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Validated singleton. Boot failures print cleanly and exit non-zero
    rather than dumping a pydantic traceback into a container log."""
    try:
        return Settings()  # values come from the environment, not the call site
    except Exception as exc:  # pragma: no cover — exercised by the boot test
        print(f"\n[config] FATAL: invalid configuration\n{exc}\n", file=sys.stderr)  # noqa: T201
        raise SystemExit(78) from exc  # EX_CONFIG


settings = get_settings()
