"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Created: ${create_date}

Reviewer checklist — every migration must answer these:

* **Is it backwards compatible?** Deploys are rolling: the old code runs
  against the new schema for several minutes. Dropping or renaming a column in
  one step breaks every pod that has not restarted yet. Expand → migrate →
  contract, across three releases.
* **Does it lock?** ``ALTER TABLE ... ADD COLUMN NOT NULL DEFAULT`` rewrites the
  whole table on older Postgres. Adding an index without ``CONCURRENTLY`` blocks
  writes for its duration.
* **Is ``downgrade`` real?** If it cannot restore the data, say so explicitly
  rather than leaving a lie that someone trusts during an incident.
* **Does a data backfill belong here?** Migrations hold a transaction open;
  a million-row UPDATE inside one is an outage. Backfill in a batched Celery
  task and keep this file to DDL.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
