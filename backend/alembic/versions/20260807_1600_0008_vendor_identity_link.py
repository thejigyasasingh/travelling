"""Join existing vendors to the identities that own them.

Repairs data, not schema. ``users.vendor_id`` and the ``vendor`` role are what
every vendor endpoint authorises against, but nothing ever wrote them: vendor
registration created the ``vendors`` row and stopped. Any vendor onboarded
before this migration can sign in, be approved, and still get
``404 VENDOR_NOT_FOUND`` from their own dashboard.

Registration now grants access as part of the same transaction. This backfills
everyone who registered before it did.

Deliberately not reversible in the destructive sense — see ``downgrade``.

Revision ID: 0008_vendor_link
Revises: 0007_review
"""

from __future__ import annotations

from alembic import op

revision = "0008_vendor_link"
down_revision = "0007_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only where the column is unset. A user already pointing at a different
    # vendor is a conflict this migration must not paper over — it would hand
    # someone another business's bookings and payouts. Left alone and visible.
    op.execute(
        """
        UPDATE users u
           SET vendor_id = v.id,
               updated_at = now()
          FROM vendors v
         WHERE v.owner_user_id = u.id
           AND u.vendor_id IS NULL
        """
    )

    # The join table is the audited source of truth; the trigger from 0002
    # mirrors it onto users.roles, which is what login reads into the token.
    op.execute(
        """
        INSERT INTO user_roles (id, user_id, role_name, granted_at)
        SELECT gen_random_uuid(), v.owner_user_id, 'vendor', now()
          FROM vendors v
        ON CONFLICT ON CONSTRAINT uq_user_roles_user_role DO NOTHING
        """
    )


def downgrade() -> None:
    """No-op, on purpose.

    The reverse would strip vendor access from live vendors, and it cannot tell
    the rows this migration wrote from the ones registration has written since.
    Rolling back the code is safe on its own: the link is inert to every other
    code path.
    """
