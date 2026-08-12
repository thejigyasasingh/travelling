"""Reusable column mixins. See Phase-3 design §5 for the full rationale.

Three audit tiers, applied by need rather than uniformly:

    TimestampMixin   -> everything except append-only event tables
    AuditMixin       -> user-mutable business data (adds created_by/updated_by)
    SoftDeleteMixin  -> ONLY the 11 tables where recovery or law requires it
    VersionMixin     -> aggregates edited concurrently (optimistic locking)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column
from uuid_utils.compat import uuid7


class UUIDPrimaryKeyMixin:
    """UUIDv7 primary key, generated application-side.

    v7 is time-ordered, so inserts are append-mostly and keep B-tree locality
    (v4 randomises every insert into a different leaf page -> page splits and
    index bloat). Generated in Python rather than by the database so a whole
    aggregate can be built in memory with its FKs wired before a single INSERT.
    """

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid7)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    # Maintained by a trigger, NOT by `onupdate=`: bulk updates, Alembic data
    # migrations and manual DBA fixes all bypass the ORM. CDC, cache
    # invalidation and incremental indexing key off this column, so an
    # `updated_at` you cannot trust is worse than none.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AuditMixin(TimestampMixin):
    @declared_attr
    @classmethod
    def created_by(cls) -> Mapped[uuid.UUID | None]:
        # Nullable + SET NULL: system/migration-created rows are legitimate,
        # and the audit trail must survive the actor being deleted.
        return mapped_column(
            PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        )

    @declared_attr
    @classmethod
    def updated_by(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(
            PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        )


class SoftDeleteMixin:
    """Apply sparingly.

    Every soft-deleted table taxes every query in the system, and one missed
    ``WHERE deleted_at IS NULL`` leaks deleted data to users. It also breaks
    unique constraints unless each one becomes a partial index filtered on
    ``deleted_at IS NULL`` — see the Phase-3 doc §5.3.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class VersionMixin:
    """Optimistic concurrency. Models must also set::

        __mapper_args__ = {"version_id_col": version}

    Pessimistic locks are wrong for listing edits — a host holds an edit form
    open for minutes, and a browser crash would leak the lock. Optimistic
    locking costs nothing when there is no conflict, which is ~99.9% of edits.
    ``SELECT ... FOR UPDATE`` is reserved for the booking transaction, whose
    critical section is milliseconds.
    """

    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class MoneyMixin:
    """Money is an integer count of minor units plus an explicit currency.

    Floats produce off-by-one-paise drift that accumulates and breaks
    reconciliation. Carrying the currency alongside the amount makes adding
    INR to USD visible in every query instead of silently wrong.
    """

    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
