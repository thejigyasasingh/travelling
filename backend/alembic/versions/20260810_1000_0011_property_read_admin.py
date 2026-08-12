"""Split `property:read:any` into public and staff reads.

`PROPERTY_READ_ANY` is held by every traveller, because browsing published
listings is what the site is for. The admin listing — every property in any
state, with the vendor behind it and the rejection reason attached — was
guarded by the same permission, so any signed-in visitor could enumerate
listings hosts had taken down.

The code catalogue in `auth/domain/rbac.py` is what actually enforces this;
these tables are the reference copy the admin UI lists. Kept in step so the two
do not disagree.

Revision ID: 0011_property_read_admin
Revises: 0010_wishlist
"""

from __future__ import annotations

from alembic import op

revision = "0011_property_read_admin"
down_revision = "0010_wishlist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, description, resource, action, scope)
        VALUES ('property:read_internal:any',
                'Read every listing in any state, including unpublished and rejected',
                'property', 'read_internal', 'any')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_name, permission_code)
        SELECT r, 'property:read_internal:any'
          FROM (VALUES ('support'), ('admin'), ('superadmin')) AS roles(r)
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_code = 'property:read_internal:any'")
    op.execute("DELETE FROM permissions WHERE code = 'property:read_internal:any'")
