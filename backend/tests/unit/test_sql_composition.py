"""The four modules that compose SQL from strings, fenced.

Most of this codebase builds queries with SQLAlchemy Core, where injection is
not reachable. Four read-model modules do not: admin analytics, vendor
reporting, property search and AI retrieval all assemble a WHERE clause,
an ORDER BY or a cursor predicate from string fragments, because the shape of
the statement genuinely varies with the request.

They are safe today. Every fragment is a literal defined in the module; every
*value* the caller supplies is a bound parameter. `ruff`'s `S608` is suppressed
per-file on exactly that basis.

**A suppression is not a guarantee.** It silences the warning for the whole
file, including the line somebody adds next year. And this is not hypothetical
for these files specifically — `admin/queries.py` already shipped a predicate
referencing two columns that do not exist, which nothing caught until someone
used the filter. The convention held; the review of it did not.

So this asserts the convention mechanically: no fragment interpolates anything
that is not a module-level constant, and every caller value is bound.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

import pytest

pytestmark = pytest.mark.unit

SRC: Final = Path(__file__).resolve().parents[2] / "src" / "app"

#: The four files that are allowed to build SQL from strings, and the constants
#: each is allowed to interpolate. Anything else in an f-string is a failure.
#:
#: Listed rather than discovered, so adding a fifth such file is a deliberate
#: act that shows up in a diff — not something that quietly inherits the
#: exemption.
COMPOSERS: Final[dict[str, set[str]]] = {
    # `where` is the clause `_filters` composes — itself fenced, by
    # `test_the_filter_builder_binds_every_value` below.
    "modules/admin/infrastructure/queries.py": {"EARNING_STATUSES", "where"},
    "modules/vendor/infrastructure/queries.py": {"EARNED"},
    "modules/property/infrastructure/search_repository.py": {
        "expr",
        "relevance_expr",
        "distance_expr",
        "order",
        "where",
        "cursor",
        "predicate",
        "joins",
        "select_extra",
        "having",
    },
    "modules/ai/infrastructure/candidates.py": {"BOOKED", "STAYED", "COLUMNS", "where"},
    # Found by the drift check below on its first run — this file carries the
    # `S608` suppression and was missing from this list, which is exactly the
    # hole the check exists to catch.
    "modules/property/infrastructure/repositories.py": set(),
}


def source_of(relative: str) -> str:
    return (SRC / relative).read_text()


def interpolations(source: str) -> list[tuple[int, str]]:
    """Every `{…}` inside an f-string **passed to `text()`**, with its line.

    Scoped to `text()` arguments, because that is the actual boundary. These
    modules also build f-strings for *values* — `f"%{query.lower()}%"` for a
    LIKE pattern, which is then bound as a parameter — and flagging those would
    make the test noise that gets deleted rather than a fence that holds.

    Parsed rather than regexed: an f-string here can span twenty lines of SQL,
    and a regex cannot tell an interpolation from the literal braces in a
    `'{}'::jsonb` cast, which these files contain.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and _is_text_call(node.func)):
            continue
        for argument in node.args:
            if isinstance(argument, ast.JoinedStr):
                for part in argument.values:
                    if isinstance(part, ast.FormattedValue):
                        found.append((part.lineno, ast.unparse(part.value)))
    return found


def _is_text_call(func: ast.expr) -> bool:
    """`text(...)` or `sa.text(...)`."""
    if isinstance(func, ast.Name):
        return func.id == "text"
    return isinstance(func, ast.Attribute) and func.attr == "text"


def module_constants(source: str) -> set[str]:
    """Names assigned at module level — the only things safe to interpolate."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


@pytest.mark.parametrize("relative", sorted(COMPOSERS), ids=lambda p: p.split("/")[1])
def test_only_constants_are_interpolated_into_sql(relative: str) -> None:
    """**The** injection fence.

    An interpolation naming anything other than a module constant or a
    locally-built clause is a request value reaching the statement text. That is
    the one thing these files must never do, and the `S608` suppression means
    no other tool is watching.
    """
    source = source_of(relative)
    allowed = COMPOSERS[relative] | module_constants(source)

    offenders = [
        f"line {line}: {{{expression}}}"
        for line, expression in interpolations(source)
        if expression not in allowed
    ]

    assert not offenders, (
        f"{relative} interpolates something that is not a module constant:\n  - "
        + "\n  - ".join(offenders)
        + "\n\nEvery caller value must be a bound parameter."
    )


def test_the_cursor_templates_take_only_a_sort_expression() -> None:
    """The one place `.format()` is used on SQL, fenced by its placeholders.

    Keyset pagination needs the cursor predicate to reference the same
    expression the ORDER BY sorts on, and for relevance and distance that
    expression is built per query. So the predicate is a template with a single
    `{expr}` hole — and the templates are module constants, so the only thing
    that can vary is which expression fills it.

    A template gaining a second placeholder is how a request value would get
    in. This asserts there is exactly one, and what it is called.
    """
    from app.modules.property.infrastructure.search_repository import _CURSOR_PREDICATE

    for sort, template in _CURSOR_PREDICATE.items():
        holes = set(re.findall(r"\{(\w+)\}", template))
        assert holes <= {"expr"}, f"{sort} template has unexpected placeholders: {holes}"


def test_the_sort_expressions_are_not_caller_supplied() -> None:
    """What fills `{expr}` has to come from the module, not the request.

    `relevance_expr` and `distance_expr` are assembled from literals and bound
    parameters inside the repository; the caller chooses a `SearchSort` enum
    member, never an expression. The enum is the fence — an unrecognised sort
    cannot index `_CURSOR_PREDICATE` at all.
    """
    from app.modules.property.application.dto import SearchSort
    from app.modules.property.infrastructure.search_repository import _CURSOR_PREDICATE

    assert set(_CURSOR_PREDICATE) == set(SearchSort), (
        "every sort must have a cursor predicate, or paging that sort raises KeyError"
    )


def test_the_filter_builder_binds_every_value() -> None:
    """`_filters` is where the admin WHERE clause is assembled.

    Its contract is that the *clause* is composed and the *value* is bound. If
    a value ever ended up in the returned string this would be the place, so it
    is asserted directly rather than inferred.
    """
    from app.modules.admin.infrastructure.queries import _filters

    where, params = _filters(
        [
            ("u.status = :status", "active'; DROP TABLE users;--", "status"),
            ("u.email LIKE :q", "%ann%", "q"),
        ]
    )

    assert "DROP TABLE" not in where
    assert where == "WHERE u.status = :status AND u.email LIKE :q"
    assert params["status"] == "active'; DROP TABLE users;--"


def test_the_filter_builder_drops_unsupplied_filters() -> None:
    """A `None` value must remove the clause, not bind a null.

    `WHERE u.status = NULL` matches nothing, silently — an admin filtering by
    nothing would get an empty table and conclude the data was gone.
    """
    where, params = _filters_for(
        [("u.status = :status", None, "status"), ("u.email = :email", "a@b.com", "email")]
    )

    assert where == "WHERE u.email = :email"
    assert "status" not in params


def test_no_filters_produces_no_where_clause() -> None:
    where, params = _filters_for([])

    assert where == ""
    assert params == {}


def _filters_for(clauses: list[tuple[str, object, str]]) -> tuple[str, dict[str, object]]:
    from app.modules.admin.infrastructure.queries import _filters

    return _filters(clauses)  # type: ignore[arg-type]


def test_every_composer_is_covered_by_the_ruff_suppression() -> None:
    """The two lists must agree.

    A file that composes SQL without an `S608` suppression would fail lint; a
    file with the suppression and no entry here has an exemption nothing checks.
    Either drift is a hole.
    """
    pyproject = (SRC.parents[1] / "pyproject.toml").read_text()
    suppressed = set(re.findall(r'"src/app/([^"]+)" = \["S608"\]', pyproject))

    assert suppressed == set(COMPOSERS), (
        f"the S608 suppressions and the fenced list disagree: {suppressed ^ set(COMPOSERS)}"
    )
