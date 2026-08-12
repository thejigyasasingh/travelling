"""Migrations must be safe to run while the previous release is still serving.

The deploy runs `migrate` to completion **before** the new API containers
start, and does not stop the old ones first. So for the length of every deploy
there is a window where the previous release's code is talking to the new
release's schema. A migration that drops or renames a column closes that window
by breaking it — during checkout, for whoever is mid-booking.

The discipline that avoids it is **expand/contract**:

* the release that needs a change ships only the *additive* half — add the
  column, backfill it, start writing to it;
* the *destructive* half — drop the old column, drop the old table — ships a
  release later, once nothing running still reads it.

A rule nobody can check is a rule that lasts until the first hurry, so this
checks it. Destructive DDL is not forbidden outright — it is required to be
**deliberate**: a migration that genuinely performs the contract half declares
`EXPAND_CONTRACT_SAFE = "…"` with a sentence saying which release did the
expand. That turns "did anyone think about this?" into a question the diff
answers.

Only `upgrade()` is checked. A `downgrade()` is destructive by definition — it
exists to undo — and is run by a human who has decided to lose the data.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.unit

VERSIONS: Final = Path(__file__).resolve().parents[2] / "alembic" / "versions"

#: Statements that break a running previous release, and the reason each does.
#:
#: `DROP INDEX` is absent deliberately: losing an index degrades a query, it
#: does not break it, and an index that turned out to be a mistake should be
#: removable without a two-release dance. `ADD COLUMN … NOT NULL` without a
#: default is present because Postgres rewrites the table and rejects existing
#: rows — it fails the migration itself, not just the old code.
DESTRUCTIVE: Final[dict[str, str]] = {
    "drop_column": "the previous release still SELECTs it",
    "drop_table": "the previous release still reads it",
    "drop_constraint": "may be re-added by the old code's writes",
    "alter_column": "a type or nullability change can reject the old code's writes",
    "rename_table": "the previous release addresses the old name",
}

#: Raw-SQL spellings of the same hazards. Migrations here use `op.execute` for
#: anything Alembic's DSL does not cover, so checking only the DSL would miss
#: most of it.
DESTRUCTIVE_SQL: Final = re.compile(
    r"\b(DROP\s+(COLUMN|TABLE)|ALTER\s+COLUMN\s+\w+\s+TYPE|RENAME\s+(COLUMN|TO))\b",
    re.IGNORECASE,
)

#: The opt-out. A migration that sets this has stated which earlier release
#: made the change safe.
MARKER: Final = "EXPAND_CONTRACT_SAFE"


def migrations() -> list[Path]:
    return sorted(p for p in VERSIONS.glob("*.py") if not p.name.startswith("__"))


def upgrade_body(path: Path) -> str:
    """The source of `upgrade()` alone.

    Parsed rather than grepped: `downgrade()` is destructive by design and
    lives in the same file, so a whole-file search would flag every migration
    that can be rolled back.
    """
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
            return ast.get_source_segment(path.read_text(), node) or ""
    return ""


def declares_marker(path: Path) -> bool:
    return MARKER in path.read_text()


def test_there_are_migrations_to_check() -> None:
    """Guards every test below from passing vacuously if the glob breaks."""
    assert len(migrations()) >= 10


@pytest.mark.parametrize("path", migrations(), ids=lambda p: p.stem)
def test_no_migration_destroys_what_the_running_release_reads(path: Path) -> None:
    """**The** deploy-safety rule.

    If this fails on a migration you meant to write, you have two options and
    the right one is almost always the first:

    1. Split it. Ship the additive half now; ship the drop next release.
    2. If the expand already happened in an earlier release, say so:

           EXPAND_CONTRACT_SAFE = "column added in 0014, unused since 0015"
    """
    if declares_marker(path):
        pytest.skip("declared as the contract half of an expand/contract pair")

    body = upgrade_body(path)
    found = [
        f"op.{operation}() — {reason}"
        for operation, reason in DESTRUCTIVE.items()
        if f"op.{operation}(" in body
    ]
    if match := DESTRUCTIVE_SQL.search(body):
        found.append(f"raw SQL {match.group(0)!r} — breaks the previous release")

    assert not found, (
        f"{path.name} performs destructive DDL in upgrade():\n  - "
        + "\n  - ".join(found)
        + f"\n\nSplit it across two releases, or declare {MARKER} with the reason."
    )


@pytest.mark.parametrize("path", migrations(), ids=lambda p: p.stem)
def test_a_declared_exception_explains_itself(path: Path) -> None:
    """The marker is an argument, not a mute button.

    A bare `EXPAND_CONTRACT_SAFE = True` would let the next person silence this
    check without thinking, which is the failure mode of every lint suppression
    ever written. It has to be a sentence.
    """
    if not declares_marker(path):
        return

    match = re.search(rf'{MARKER}\s*=\s*["\'](.+?)["\']', path.read_text(), re.DOTALL)
    assert match, f"{path.name}: {MARKER} must be a string explaining why"
    assert len(match.group(1).strip()) >= 20, (
        f"{path.name}: {MARKER} needs a real reason, not {match.group(1)!r}"
    )


@pytest.mark.parametrize("path", migrations(), ids=lambda p: p.stem)
def test_every_migration_can_be_rolled_back(path: Path) -> None:
    """A deploy that cannot be undone is a deploy nobody wants to make at 5pm.

    An intentionally irreversible migration still needs a `downgrade()` — one
    that raises with a reason, so the failure is a sentence rather than an
    `AttributeError` from Alembic.
    """
    source = path.read_text()

    assert "def downgrade()" in source, f"{path.name} has no downgrade()"


def test_revision_identifiers_are_unique() -> None:
    """Two migrations sharing a revision id gives Alembic two heads, and the
    deploy stops with a message that does not name either file."""
    revisions: dict[str, str] = {}
    for path in migrations():
        # The annotation is optional: the baseline writes
        # `revision: str = "..."`, later files write `revision = "..."`.
        match = re.search(
            r'^revision(?:\s*:\s*[\w |\[\]]+)?\s*=\s*["\'](.+?)["\']',
            path.read_text(),
            re.MULTILINE,
        )
        assert match, f"{path.name} declares no revision id"
        revision = match.group(1)
        assert revision not in revisions, (
            f"{path.name} reuses revision {revision!r} from {revisions[revision]}"
        )
        revisions[revision] = path.name


def test_the_migration_chain_is_linear() -> None:
    """One head, no branches.

    A branch is two migrations claiming the same parent. Alembic refuses to
    upgrade past it, and the error arrives during a deploy rather than during
    review.
    """
    parents: dict[str, str] = {}
    for path in migrations():
        source = path.read_text()
        down = re.search(
            r'^down_revision(?:\s*:\s*[\w |\[\]]+)?\s*=\s*(?:["\'](.+?)["\']|None)',
            source,
            re.MULTILINE,
        )
        assert down, f"{path.name} declares no down_revision"
        parent = down.group(1)
        # The baseline has no parent — `None` matches the alternation with no
        # capture group, which is how the root of the chain is identified.
        if parent is None:
            continue
        assert parent not in parents, (
            f"{path.name} and {parents[parent]} both descend from {parent!r} — "
            "that is a branch, and Alembic will refuse to upgrade past it"
        )
        parents[parent] = path.name
