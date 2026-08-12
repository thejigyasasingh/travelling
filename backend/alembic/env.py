"""Alembic environment.

Decisions that are not the Alembic default, and why:

**Synchronous psycopg, not asyncpg.** Migrations are a one-shot batch job run
by an init container. Async buys nothing, and the sync path is what every
Alembic recipe and every DBA expects when they need to intervene manually.
``Settings.sync_dsn`` derives it from the same DSN the app uses, so the two
cannot drift.

**Migration-specific timeouts.** ``lock_timeout`` is 5 s: a migration that
cannot get its lock within 5 seconds must fail fast, because while it waits it
*queues every subsequent query on that table behind it* — a 30-second lock wait
on ``users`` is a 30-second outage. ``statement_timeout`` is 0 (unlimited)
because a legitimate index build on a large table can run for many minutes and
must not be killed halfway.

**``compare_type`` and ``compare_server_default`` on.** Autogenerate silently
misses a ``VARCHAR(50)`` → ``VARCHAR(100)`` change without them, and the
migration that "worked" then truncates production data.

**Alembic's own tables and PostGIS internals are excluded** from autogenerate,
or every run produces a diff trying to drop ``spatial_ref_sys``.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path
from typing import Any

from alembic import context
from sqlalchemy import create_engine, pool, text

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from app.core.config import get_settings  # noqa: E402

# Import every module that defines a table, so `Base.metadata` is complete.
# An omission here means autogenerate produces a migration that DROPS the
# missing table — the single most dangerous failure mode in this file.
from app.infrastructure.database import outbox  # noqa: E402, F401
from app.infrastructure.database.base import Base  # noqa: E402
from app.modules.ai.infrastructure import models as ai_models  # noqa: E402, F401
from app.modules.auth.infrastructure import models as auth_models  # noqa: E402, F401
from app.modules.booking.infrastructure import models as booking_models  # noqa: E402, F401
from app.modules.coupon.infrastructure import models as coupon_models  # noqa: E402, F401
from app.modules.notification.infrastructure import models as notif_models  # noqa: E402, F401
from app.modules.payment.infrastructure import models as payment_models  # noqa: E402, F401
from app.modules.property.infrastructure import models as property_models  # noqa: E402, F401
from app.modules.review.infrastructure import models as review_models  # noqa: E402, F401
from app.modules.support.infrastructure import models as support_models  # noqa: E402, F401
from app.modules.vendor.infrastructure import models as vendor_models  # noqa: E402, F401
from app.modules.wishlist.infrastructure import models as wishlist_models  # noqa: E402, F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

EXCLUDED_TABLES = {
    "spatial_ref_sys",  # PostGIS
    "geography_columns",
    "geometry_columns",
    "alembic_version",
}
EXCLUDED_SCHEMAS = {"information_schema", "pg_catalog", "tiger", "topology"}


def include_object(
    obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    if type_ == "table" and name in EXCLUDED_TABLES:
        return False
    return getattr(obj, "schema", None) not in EXCLUDED_SCHEMAS


def _url() -> str:
    return get_settings().database.sync_dsn


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing it.

    Used by the CI gate that requires a human to read the SQL of any migration
    touching a table above a size threshold, and by DBAs who apply changes to
    production themselves during a maintenance window.
    """
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=include_object,
        include_schemas=False,
        version_table="alembic_version",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        _url(),
        poolclass=pool.NullPool,  # one-shot job; a pool is pointless overhead
        future=True,
    )

    with engine.connect() as connection:
        # See the module docstring. These are per-session and revert when the
        # connection closes.
        connection.execute(text("SET lock_timeout = '5s'"))
        connection.execute(text("SET statement_timeout = 0"))
        connection.execute(text("SET idle_in_transaction_session_timeout = '60s'"))

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_object=include_object,
            # One transaction for the whole upgrade: a migration that fails
            # halfway rolls back entirely rather than leaving the schema in a
            # state no migration file describes.
            transaction_per_migration=False,
            render_as_batch=False,  # a Postgres-only codebase; batch mode is for SQLite
        )

        with context.begin_transaction():
            context.run_migrations()

        # REQUIRED on SQLAlchemy 2.0. When a connection is handed to
        # `context.configure`, Alembic treats the caller as the owner of the
        # transaction and does not commit — and SQLAlchemy 2.0 removed the
        # implicit autocommit that used to paper over this. Without it,
        # `alembic upgrade head` prints every "Running upgrade …" line, exits
        # zero, and applies precisely nothing.
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
