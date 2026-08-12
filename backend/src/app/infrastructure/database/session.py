"""Database engines and session factories.

The write/read split is deliberate and physical rather than a routing flag:

* ``get_write_session()`` -> primary. Every mutation, and any read inside a
  transaction that a mutation depends on (availability checks, balance reads).
* ``get_read_session()``  -> replica. Search, listings, reporting.

Replication lag is 10-200 ms and worse under load. A booking that read
availability from a replica would corrupt inventory. Two named callables make
that choice explicit at every call site instead of hiding it in config where
somebody eventually gets it wrong.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _engine_kwargs(settings: Settings) -> dict[str, Any]:
    db = settings.database
    kwargs: dict[str, Any] = {
        "echo": db.echo_sql,
        "pool_pre_ping": db.pool_pre_ping,
        "pool_recycle": db.pool_recycle_seconds,
        "connect_args": {
            # Per-connection guardrails. `lock_timeout` in particular is what
            # stops a stray DDL or a long lock wait from queueing the whole
            # application behind it.
            "server_settings": {
                "application_name": f"{settings.app_name}",
                "statement_timeout": str(db.statement_timeout_ms),
                "lock_timeout": str(db.lock_timeout_ms),
                "idle_in_transaction_session_timeout": "30000",
                "jit": "off",  # JIT hurts our short OLTP queries more than it helps
            },
            # asyncpg caches prepared statements per connection; pgbouncer in
            # transaction mode cannot support that. Disabled for portability.
            "statement_cache_size": 0,
        },
    }

    if settings.app_env.value == "test":
        # NullPool: each test gets a clean connection, no cross-test state.
        kwargs["poolclass"] = NullPool
    else:
        kwargs |= {
            "pool_size": db.pool_size,
            "max_overflow": db.max_overflow,
            "pool_timeout": db.pool_timeout_seconds,
        }
    return kwargs


class Database:
    """Owns engine lifecycle. Constructed once, in the container."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

        self.write_engine: AsyncEngine = create_async_engine(
            str(settings.database.dsn), **_engine_kwargs(settings)
        )
        # A distinct engine even when the DSN is identical (local dev): the
        # code path must be the same everywhere so a replica appearing in
        # staging changes configuration, not code.
        self.read_engine: AsyncEngine = create_async_engine(
            str(settings.database.read_dsn), **_engine_kwargs(settings)
        )

        self.write_session_factory = async_sessionmaker(
            bind=self.write_engine,
            class_=AsyncSession,
            expire_on_commit=False,  # entities stay usable after commit
            autoflush=False,  # flush timing is the Unit of Work's business
        )
        self.read_session_factory = async_sessionmaker(
            bind=self.read_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        self._install_read_only_guard()

    def _install_read_only_guard(self) -> None:
        """Make "writes never touch a replica" a runtime guarantee.

        A `SET default_transaction_read_only` on the replica connection turns
        an accidental write into an immediate, loud error instead of a
        silently-lagged read or a write to the wrong node.
        """

        @event.listens_for(self.read_engine.sync_engine, "connect")
        def _set_read_only(dbapi_conn: Any, _record: Any) -> None:  # pragma: no cover
            if self._settings.database.replica_dsn is None:
                return  # local dev: same node, guard would break migrations
            cur = dbapi_conn.cursor()
            cur.execute("SET default_transaction_read_only = on")
            cur.close()

    async def ping(self, *, replica: bool = False) -> bool:
        engine = self.read_engine if replica else self.write_engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True

    async def dispose(self) -> None:
        await self.write_engine.dispose()
        await self.read_engine.dispose()
        logger.info("database_disposed")

    # ── session scopes ────────────────────────────────────────────────────

    @asynccontextmanager
    async def write_session(self) -> AsyncIterator[AsyncSession]:
        """Transactional scope. Commits on success, rolls back on any raise.

        Callers never call ``commit()`` themselves; the scope owns the
        transaction boundary so a half-committed unit of work is not
        expressible.
        """
        session = self.write_session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def read_session(self) -> AsyncIterator[AsyncSession]:
        session = self.read_session_factory()
        try:
            yield session
        finally:
            await session.close()
