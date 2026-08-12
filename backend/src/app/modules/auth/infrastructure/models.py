"""Auth persistence models.

These are **not** the domain entities. They are row shapes, mapped across by
``mappers.py``. The translation costs a little code and buys the property that
a schema change cannot silently alter a business rule — and that the lockout
logic in ``domain/entities.py`` can be tested without a database.

Index and constraint choices are commented where the reason is not obvious;
each one exists because of a specific query on a specific hot path.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import (
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    VersionMixin,
)


class UserModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin):
    __tablename__ = "users"

    # ── identity ──────────────────────────────────────────────────────────
    # CITEXT, not lower(email) on a functional index. The column *is* the
    # case-insensitive value, so every query, join and foreign key gets the
    # behaviour without anyone remembering to wrap it in lower().
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    phone_e164: Mapped[str | None] = mapped_column(String(16))
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── credentials ───────────────────────────────────────────────────────
    # Nullable: an account that only ever signed in with Google has no
    # password, and NULL says that in a way an empty string does not.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ── profile ───────────────────────────────────────────────────────────
    full_name: Mapped[str | None] = mapped_column(String(150))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    locale: Mapped[str] = mapped_column(String(10), server_default=text("'en-IN'"))
    timezone: Mapped[str] = mapped_column(String(50), server_default=text("'Asia/Kolkata'"))

    # ── status ────────────────────────────────────────────────────────────
    # A plain constrained VARCHAR rather than a Postgres ENUM: adding a value
    # to an ENUM takes a lock and cannot be done inside a transaction with
    # other DDL, which makes an otherwise trivial migration awkward. A CHECK
    # constraint gives the same guarantee and alters freely.
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'pending_verification'")
    )
    suspension_reason: Mapped[str | None] = mapped_column(Text)
    signup_method: Mapped[str] = mapped_column(String(20), server_default=text("'password'"))

    # ── roles ─────────────────────────────────────────────────────────────
    # Denormalised onto the user row as a text array, *in addition* to the
    # user_roles join table. Every login reads roles to stamp them into the
    # access token; a join per login is a join we can avoid entirely. The join
    # table remains the audited source of truth (who granted what, when) and a
    # trigger keeps this column in step — see migration 0002.
    roles: Mapped[list[str]] = mapped_column(
        ARRAY(String(30)), nullable=False, server_default=text("ARRAY['traveler']::varchar[]")
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))

    # ── lockout ───────────────────────────────────────────────────────────
    failed_login_attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    lockout_level: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Enables optimistic locking. SQLAlchemy reads this by name — it is a
    # framework contract, not the kind of mutable class default RUF012 means.
    __mapper_args__ = {"version_id_col": VersionMixin.version}  # noqa: RUF012

    __table_args__ = (
        # Partial unique index, not a plain UNIQUE. A soft-deleted user still
        # occupies the row; without the filter, nobody could ever re-register
        # with an address that was once deleted, and GDPR erasure would
        # permanently burn the address.
        Index(
            "uq_users_email_active",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_users_phone_active",
            "phone_e164",
            unique=True,
            postgresql_where=text("phone_e164 IS NOT NULL AND deleted_at IS NULL"),
        ),
        CheckConstraint(
            "status IN ('pending_verification','active','suspended','deactivated')",
            name="status_valid",
        ),
        CheckConstraint("signup_method IN ('password','google','otp')", name="signup_method_valid"),
        CheckConstraint(
            "phone_e164 IS NULL OR phone_e164 ~ '^\\+[1-9][0-9]{7,14}$'", name="phone_e164"
        ),
        # Same rule as the domain's `has_password`, enforced by the database so
        # a bad data migration cannot create an account nobody can sign in to.
        CheckConstraint(
            "password_hash IS NOT NULL OR signup_method IN ('google','otp')",
            name="credential_present",
        ),
        # Supports the admin user list and the "locked accounts" ops view.
        Index("ix_users_status_created", "status", "created_at"),
        Index("ix_users_vendor", "vendor_id", postgresql_where=text("vendor_id IS NOT NULL")),
        Index("ix_users_locked", "locked_until", postgresql_where=text("locked_until IS NOT NULL")),
    )


class SessionModel(Base, UUIDPrimaryKeyMixin):
    """One refresh token. See ``domain/entities.Session`` for the rotation rules."""

    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The rotation chain. Not a foreign key to itself for the family — every
    # member shares the value, and there is no single "family" row.
    family_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))

    # SHA-256 hex. Never the token itself — a database dump must not yield
    # working sessions. See tokens.py for why this is not Argon2.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(50))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    ip_hash: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    device_label: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        # THE hot path: every refresh is a lookup by hash. Unique because two
        # rows sharing a token hash would make "which session is this?"
        # ambiguous at exactly the wrong moment.
        UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
        # Family revocation on reuse detection — must be a single index scan,
        # because it runs while an attacker is mid-request.
        Index("ix_auth_sessions_family", "family_id"),
        # "Sign me out everywhere", and the sessions list. Partial: revoked and
        # rotated rows are the overwhelming majority after a few weeks and are
        # never listed.
        Index(
            "ix_auth_sessions_user_active",
            "user_id",
            "expires_at",
            postgresql_where=text("revoked_at IS NULL AND rotated_at IS NULL"),
        ),
        # Drives the nightly purge of dead rows.
        Index("ix_auth_sessions_expires", "expires_at"),
        CheckConstraint("expires_at > issued_at", name="expiry_after_issue"),
    )


class OAuthAccountModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "oauth_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    # Google's "sub". Stable for the lifetime of the Google account and, unlike
    # the email, never reassigned — which is why lookups key on it.
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(CITEXT)
    raw_profile: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # One provider account maps to at most one user. Without this, two
        # local accounts could both claim the same Google identity and sign-in
        # would resolve to whichever row came back first.
        UniqueConstraint(
            "provider", "provider_account_id", name="uq_oauth_accounts_provider_account"
        ),
        # A user links each provider at most once.
        UniqueConstraint("user_id", "provider", name="uq_oauth_accounts_user_provider"),
        CheckConstraint("provider IN ('google','apple','facebook')", name="provider_valid"),
    )


class ActionTokenModel(Base):
    """Spent single-use tokens (email verification, password reset).

    Records only the ``jti``, and only *after* use. Storing unused tokens would
    mean a table of live credentials; storing spent ones is a deny-list that
    reveals nothing if leaked.
    """

    __tablename__ = "auth_action_tokens"

    # The jti IS the primary key. That makes "spend this token" a plain INSERT
    # whose uniqueness violation means "already used" — atomic without a
    # transaction dance, which matters because two concurrent clicks on the
    # same reset link must not both win.
    jti: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    spent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Once past this, the token would be rejected on expiry anyway, so the row
    # can be purged. Without it this table grows forever.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_auth_action_tokens_purge", "expires_at"),
        Index("ix_auth_action_tokens_user", "user_id", "purpose"),
        CheckConstraint("purpose IN ('email_verify','password_reset')", name="purpose_valid"),
    )


# ══════════════════════════════════════════════════════════════════════════
# RBAC projection
#
# `roles` and `permissions` mirror the catalogue in `domain/rbac.py`, which
# remains the source of truth (see that module for why). These rows exist so an
# admin UI can list them and `user_roles` can carry a real foreign key.
# ══════════════════════════════════════════════════════════════════════════


class RoleModel(Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(30), primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    # True for everything seeded from rbac.py. A migration refuses to drop
    # these, and the admin UI hides their edit controls — changing them here
    # would have no effect, since authorisation reads the code.
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    rank: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class PermissionModel(Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(60), primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    resource: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (Index("ix_permissions_resource", "resource"),)


class RolePermissionModel(Base):
    __tablename__ = "role_permissions"

    role_name: Mapped[str] = mapped_column(
        String(30), ForeignKey("roles.name", ondelete="CASCADE"), primary_key=True
    )
    permission_code: Mapped[str] = mapped_column(
        String(60), ForeignKey("permissions.code", ondelete="CASCADE"), primary_key=True
    )


class UserRoleModel(Base, UUIDPrimaryKeyMixin):
    """Who holds which role, and who granted it.

    The audited record. ``users.roles`` is the read-optimised copy.
    """

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_name: Mapped[str] = mapped_column(
        String(30), ForeignKey("roles.name", ondelete="RESTRICT"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # SET NULL, not CASCADE: the audit trail must survive the granting admin
    # being deleted, or offboarding an employee erases the evidence of what
    # they did.
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    __table_args__ = (
        UniqueConstraint("user_id", "role_name", name="uq_user_roles_user_role"),
        Index("ix_user_roles_role", "role_name"),
    )
