"""Configuration as a deployment actually supplies it.

Every test here is a regression for a bug that stopped the container starting,
and every one of them was found by taking the production compose file and
constructing `Settings` from it rather than by reading either.

The pattern they share: **an environment variable is a string, and an unset one
is an empty string.** The type system says `list[str]` and `PostgresDsn | None`,
and neither of those is what arrives. The failures all happen at boot, on the
first deploy to a new environment, with a message that names the section and
not the reason.

The other half is the production safety validator. It refuses to construct with
a wildcard host allowlist, and that is correct — but it means the compose file
*must* supply one, which is not obvious from either file alone.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import DatabaseSettings, HTTPSettings

pytestmark = pytest.mark.unit

PRIMARY = "postgresql+asyncpg://u:p@primary:5432/db"


# ══════════════════════════════════════════════════════════════════════════
# List settings from the environment
# ══════════════════════════════════════════════════════════════════════════


def test_comma_separated_origins_are_accepted() -> None:
    """The form every deployment guide shows and every operator types.

    Before this, `CORS_ORIGINS=https://a,https://b` raised inside the
    environment source — before any validator — and the process exited naming
    only the `http` section.
    """
    settings = HTTPSettings(cors_origins="https://a.example, https://b.example")
    assert settings.cors_origins == ["https://a.example", "https://b.example"]


def test_json_origins_still_work() -> None:
    """The existing `.env` files use JSON and must keep working. A fix that
    trades one accepted format for another is not a fix."""
    settings = HTTPSettings(cors_origins='["https://a.example","https://b.example"]')
    assert settings.cors_origins == ["https://a.example", "https://b.example"]


def test_a_single_origin_is_a_list_of_one() -> None:
    assert HTTPSettings(cors_origins="https://a.example").cors_origins == ["https://a.example"]


def test_an_empty_origins_value_is_an_empty_list() -> None:
    """An unset compose variable arrives as `""`. It means "none configured",
    not "invalid"."""
    assert HTTPSettings(cors_origins="").cors_origins == []
    assert HTTPSettings(cors_origins="   ").cors_origins == []


def test_whitespace_around_entries_is_trimmed() -> None:
    """`a, b, c` is what a human writes. A leading space in an origin makes it
    match nothing, and CORS failures are debugged in a browser console rather
    than in a log."""
    assert HTTPSettings(cors_origins=" https://a.example ,  https://b.example ").cors_origins == [
        "https://a.example",
        "https://b.example",
    ]


def test_a_native_list_passes_through() -> None:
    """Constructed in code and in tests, not only from the environment."""
    assert HTTPSettings(cors_origins=["https://a.example"]).cors_origins == ["https://a.example"]


def test_allowed_hosts_takes_the_same_forms() -> None:
    """The two fields fail identically, so they are fixed identically. Fixing
    only the one that bit you leaves the other waiting."""
    assert HTTPSettings(allowed_hosts="a.example,b.example").allowed_hosts == [
        "a.example",
        "b.example",
    ]


def test_malformed_json_falls_back_to_splitting() -> None:
    """A truncated or hand-edited value should degrade to something usable
    rather than refusing to boot. `["a", "b"` is a typo, not a reason to take
    the site down."""
    assert HTTPSettings(cors_origins='["https://a.example", "https://b.example"').cors_origins == [
        "https://a.example",
        "https://b.example",
    ]


# ══════════════════════════════════════════════════════════════════════════
# Optional settings that arrive blank
# ══════════════════════════════════════════════════════════════════════════


def test_a_blank_replica_dsn_means_no_replica() -> None:
    """`DATABASE__REPLICA_DSN: ${DATABASE_REPLICA_DSN:-}` is the natural way to
    write an optional setting in compose, and it delivers `""`.

    Without this the container refuses to start on a single-node deployment —
    the configuration that is *most* likely to leave it unset.
    """
    settings = DatabaseSettings(dsn=PRIMARY, replica_dsn="")
    assert settings.replica_dsn is None
    assert str(settings.read_dsn) == PRIMARY


def test_a_real_replica_is_used_for_reads() -> None:
    replica = "postgresql+asyncpg://u:p@replica:5432/db"
    settings = DatabaseSettings(dsn=PRIMARY, replica_dsn=replica)
    assert str(settings.read_dsn) == replica


def test_reads_fall_back_to_the_primary_rather_than_failing() -> None:
    """Never fails closed. A missing replica must degrade to slower reads, not
    to no reads."""
    assert str(DatabaseSettings(dsn=PRIMARY).read_dsn) == PRIMARY


def test_a_malformed_replica_dsn_is_still_rejected() -> None:
    """Blank means "unset". Anything else that is not a DSN is a typo, and
    silently falling back would hide it until someone wondered why the replica
    was idle."""
    with pytest.raises(ValidationError):
        DatabaseSettings(dsn=PRIMARY, replica_dsn="not-a-dsn")


# ══════════════════════════════════════════════════════════════════════════
# The production safety validator
# ══════════════════════════════════════════════════════════════════════════


def test_a_wildcard_host_allowlist_is_refused_in_production(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The `["*"]` default is for local development.

    In production the application builds absolute URLs — password resets,
    invoices — from the Host header, so a wildcard lets an attacker send
    `Host: evil.example` and choose where those links point.

    The consequence for deployment, which is why this test exists: the compose
    file **must** supply `HTTP__ALLOWED_HOSTS`. Neither file says so on its
    own, and the failure is a container that will not start.
    """
    from app.core.config import Settings

    for key, value in {
        "APP_ENV": "production",
        "DEBUG": "false",
        "LOG_FORMAT": "json",
        "DATABASE__DSN": PRIMARY,
        "REDIS__URL": "redis://redis:6379",
        "HTTP__ALLOWED_HOSTS": "*",
        "HTTP__CORS_ORIGINS": "https://a.example",
        "PAYMENT__ENABLED": "false",
    }.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ValidationError, match="ALLOWED_HOSTS"):
        Settings()
