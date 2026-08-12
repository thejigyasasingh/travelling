"""auth: users, sessions, oauth, action tokens, RBAC

Revision ID: 0002_auth
Revises: 0001_baseline
Created: 2026-08-06 14:00:00+00:00

Reviewer notes on the non-obvious choices:

* **Partial unique indexes on email and phone**, filtered on
  ``deleted_at IS NULL``. A plain UNIQUE would mean a soft-deleted account
  permanently burns its email address — nobody could ever register with it
  again, and GDPR erasure would make that permanent.
* **``users.roles`` is denormalised** alongside the ``user_roles`` join table.
  Every login reads roles to stamp the access token; a join per login is a join
  worth avoiding. The join table stays the audited source of truth and a
  trigger keeps the array in step, so the two cannot silently diverge.
* **Roles and permissions are seeded from ``domain/rbac.py``**, which remains
  the authority. These rows exist so an admin UI can list them and
  ``user_roles`` can carry a real foreign key — editing them changes nothing
  about what anyone is allowed to do.
* **``auth_action_tokens`` has the ``jti`` as its primary key**, which turns
  "spend this token" into an INSERT whose conflict means "already used" —
  atomic without a transaction dance. Two concurrent clicks on the same reset
  link must not both win.

This migration is additive only: no existing table is touched, so it is safe to
apply before the new code is deployed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_auth"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Keeps `users.roles` in step with the audited `user_roles` rows. Written as a
# trigger rather than left to the application: a data migration, an admin
# running SQL, or a second service would all bypass application code, and a
# `roles` array that disagrees with `user_roles` is a silent privilege bug.
SYNC_ROLES_FN = """
CREATE OR REPLACE FUNCTION sync_user_roles()
RETURNS TRIGGER AS $$
DECLARE
    target_user uuid;
BEGIN
    target_user := COALESCE(NEW.user_id, OLD.user_id);
    UPDATE users
       SET roles = COALESCE(
               (SELECT array_agg(role_name ORDER BY role_name)
                  FROM user_roles WHERE user_id = target_user),
               ARRAY['traveler']::varchar[]
           )
     WHERE id = target_user;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""

# name, description, rank — mirrors domain/rbac.py
ROLES = [
    ("traveler", "Books stays and activities", 0),
    ("vendor_staff", "Manages listings on behalf of a vendor", 10),
    ("vendor", "Owns properties and receives payouts", 20),
    ("support", "Assists users; can read and cancel bookings", 30),
    ("admin", "Platform operations", 40),
    ("superadmin", "Grants roles and changes platform settings", 50),
    ("system", "Background jobs. Never assignable to a person.", 99),
]


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("phone_e164", sa.String(length=16)),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True)),
        sa.Column("password_hash", sa.String(length=255)),
        sa.Column("password_changed_at", sa.DateTime(timezone=True)),
        sa.Column("full_name", sa.String(length=150)),
        sa.Column("avatar_url", sa.String(length=500)),
        sa.Column(
            "locale", sa.String(length=10), server_default=sa.text("'en-IN'"), nullable=False
        ),
        sa.Column(
            "timezone",
            sa.String(length=50),
            server_default=sa.text("'Asia/Kolkata'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default=sa.text("'pending_verification'"),
            nullable=False,
        ),
        sa.Column("suspension_reason", sa.Text()),
        sa.Column(
            "signup_method",
            sa.String(length=20),
            server_default=sa.text("'password'"),
            nullable=False,
        ),
        sa.Column(
            "roles",
            postgresql.ARRAY(sa.String(length=30)),
            server_default=sa.text("ARRAY['traveler']::varchar[]"),
            nullable=False,
        ),
        sa.Column("vendor_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "failed_login_attempts", sa.SmallInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("lockout_level", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.CheckConstraint(
            "status IN ('pending_verification','active','suspended','deactivated')",
            name=op.f("ck_users_status_valid"),
        ),
        sa.CheckConstraint(
            "signup_method IN ('password','google','otp')",
            name=op.f("ck_users_signup_method_valid"),
        ),
        sa.CheckConstraint(
            r"phone_e164 IS NULL OR phone_e164 ~ '^\+[1-9][0-9]{7,14}$'",
            name=op.f("ck_users_phone_e164"),
        ),
        # Mirrors the domain's `has_password`: an account with no password must
        # have another way in, or it is unreachable by anyone.
        sa.CheckConstraint(
            "password_hash IS NOT NULL OR signup_method IN ('google','otp')",
            name=op.f("ck_users_credential_present"),
        ),
    )

    op.create_index(
        "uq_users_email_active",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_users_phone_active",
        "users",
        ["phone_e164"],
        unique=True,
        postgresql_where=sa.text("phone_e164 IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index("ix_users_status_created", "users", ["status", "created_at"])
    op.create_index("ix_users_created_at", "users", ["created_at"])
    op.create_index(
        "ix_users_vendor",
        "users",
        ["vendor_id"],
        postgresql_where=sa.text("vendor_id IS NOT NULL"),
    )
    op.create_index(
        "ix_users_locked",
        "users",
        ["locked_until"],
        postgresql_where=sa.text("locked_until IS NOT NULL"),
    )
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])

    op.execute(
        "CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # ── sessions ──────────────────────────────────────────────────────────
    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True)),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(length=50)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("ip_hash", sa.String(length=64)),
        sa.Column("user_agent", sa.String(length=400)),
        sa.Column("device_label", sa.String(length=100)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
        sa.CheckConstraint(
            "expires_at > issued_at", name=op.f("ck_auth_sessions_expiry_after_issue")
        ),
    )
    # Family revocation runs while an attacker holds a live token; it must be a
    # single index scan.
    op.create_index("ix_auth_sessions_family", "auth_sessions", ["family_id"])
    op.create_index(
        "ix_auth_sessions_user_active",
        "auth_sessions",
        ["user_id", "expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL AND rotated_at IS NULL"),
    )
    op.create_index("ix_auth_sessions_expires", "auth_sessions", ["expires_at"])

    # ── oauth ─────────────────────────────────────────────────────────────
    op.create_table(
        "oauth_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("email", postgresql.CITEXT()),
        sa.Column(
            "raw_profile",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "linked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_accounts")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_oauth_accounts_user_id_users"),
            ondelete="CASCADE",
        ),
        # Without this, two local accounts could both claim the same Google
        # identity and sign-in would resolve to whichever row came back first.
        sa.UniqueConstraint(
            "provider", "provider_account_id", name="uq_oauth_accounts_provider_account"
        ),
        sa.UniqueConstraint("user_id", "provider", name="uq_oauth_accounts_user_provider"),
        sa.CheckConstraint(
            "provider IN ('google','apple','facebook')",
            name=op.f("ck_oauth_accounts_provider_valid"),
        ),
    )
    op.create_index("ix_oauth_accounts_created_at", "oauth_accounts", ["created_at"])

    # ── single-use action tokens ──────────────────────────────────────────
    op.create_table(
        "auth_action_tokens",
        sa.Column("jti", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column(
            "spent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("jti", name=op.f("pk_auth_action_tokens")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_action_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "purpose IN ('email_verify','password_reset')",
            name=op.f("ck_auth_action_tokens_purpose_valid"),
        ),
    )
    op.create_index("ix_auth_action_tokens_purge", "auth_action_tokens", ["expires_at"])
    op.create_index("ix_auth_action_tokens_user", "auth_action_tokens", ["user_id", "purpose"])

    # ── RBAC projection ───────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("name", sa.String(length=30), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("rank", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_roles")),
    )
    op.create_table(
        "permissions",
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("resource", sa.String(length=30), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_permissions")),
    )
    op.create_index("ix_permissions_resource", "permissions", ["resource"])

    op.create_table(
        "role_permissions",
        sa.Column("role_name", sa.String(length=30), nullable=False),
        sa.Column("permission_code", sa.String(length=60), nullable=False),
        sa.PrimaryKeyConstraint("role_name", "permission_code", name=op.f("pk_role_permissions")),
        sa.ForeignKeyConstraint(
            ["role_name"],
            ["roles.name"],
            name=op.f("fk_role_permissions_role_name_roles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_code"],
            ["permissions.code"],
            name=op.f("fk_role_permissions_permission_code_permissions"),
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_name", sa.String(length=30), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True)),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["role_name"],
            ["roles.name"],
            name=op.f("fk_user_roles_role_name_roles"),
            ondelete="RESTRICT",
        ),
        # SET NULL, not CASCADE: the audit trail must survive the granting
        # admin being deleted, or offboarding erases the evidence.
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name=op.f("fk_user_roles_granted_by_users"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("user_id", "role_name", name="uq_user_roles_user_role"),
    )
    op.create_index("ix_user_roles_role", "user_roles", ["role_name"])

    # ── seed the RBAC projection ──────────────────────────────────────────
    _seed_rbac()

    # ── keep users.roles in step ──────────────────────────────────────────
    op.execute(SYNC_ROLES_FN)
    op.execute(
        "CREATE TRIGGER trg_user_roles_sync "
        "AFTER INSERT OR UPDATE OR DELETE ON user_roles "
        "FOR EACH ROW EXECUTE FUNCTION sync_user_roles()"
    )


def _seed_rbac() -> None:
    """Project the catalogue in ``domain/rbac.py`` into rows.

    Imported rather than hand-listed so the seed cannot drift from the code
    that actually enforces authorisation — a hand-maintained copy would be
    wrong within two sprints.
    """
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from app.modules.auth.domain.rbac import ROLE_PERMISSIONS, Permission

    conn = op.get_bind()

    conn.execute(
        sa.text(
            "INSERT INTO roles (name, description, is_system, rank) "
            "VALUES (:name, :description, true, :rank)"
        ),
        [{"name": n, "description": d, "rank": r} for n, d, r in ROLES],
    )

    conn.execute(
        sa.text(
            "INSERT INTO permissions (code, description, resource, action, scope) "
            "VALUES (:code, :description, :resource, :action, :scope)"
        ),
        [
            {
                "code": p.value,
                "description": p.name.replace("_", " ").title(),
                "resource": p.value.split(":")[0],
                "action": p.value.split(":")[1],
                "scope": p.value.split(":")[2],
            }
            for p in Permission
        ],
    )

    rows = [
        {"role_name": role.value, "permission_code": perm.value}
        for role, perms in ROLE_PERMISSIONS.items()
        for perm in perms
    ]
    if rows:
        conn.execute(
            sa.text(
                "INSERT INTO role_permissions (role_name, permission_code) "
                "VALUES (:role_name, :permission_code)"
            ),
            rows,
        )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_user_roles_sync ON user_roles")
    op.execute("DROP FUNCTION IF EXISTS sync_user_roles()")
    op.execute("DROP TRIGGER IF EXISTS trg_users_updated_at ON users")

    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("auth_action_tokens")
    op.drop_table("oauth_accounts")
    op.drop_table("auth_sessions")
    op.drop_table("users")
