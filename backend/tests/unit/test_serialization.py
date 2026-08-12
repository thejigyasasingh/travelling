"""DTO serialisation, and the bug it exists to prevent.

Every router maps its application DTOs onto response models. It used to do that
with ``vars()`` — which returns ``__dict__``, which a ``@dataclass(slots=True)``
does not have. Every DTO in this codebase is slotted, so **every
response-returning endpoint raised TypeError**. It survived four phases of
tests because those tests called use cases directly and never went through a
router.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.core.serialization import dto_dict

pytestmark = pytest.mark.unit


@dataclass(frozen=True, slots=True)
class Inner:
    value: int


@dataclass(frozen=True, slots=True)
class Slotted:
    name: str
    secret_key: str
    inner: Inner


@dataclass(frozen=True)
class Unslotted:
    name: str


def test_reads_a_slotted_dataclass() -> None:
    """The whole point. ``vars()`` raises here."""
    result = dto_dict(Slotted(name="villa", secret_key="k", inner=Inner(1)))
    assert result["name"] == "villa"

    with pytest.raises(TypeError):
        vars(Slotted(name="villa", secret_key="k", inner=Inner(1)))


def test_reads_an_unslotted_dataclass_too() -> None:
    assert dto_dict(Unslotted(name="villa")) == {"name": "villa"}


def test_excludes_fields_that_must_not_reach_the_wire() -> None:
    result = dto_dict(
        Slotted(name="villa", secret_key="k", inner=Inner(1)), exclude=frozenset({"secret_key"})
    )
    assert "secret_key" not in result
    assert result["name"] == "villa"


def test_does_not_recurse_into_nested_dataclasses() -> None:
    """Shallow on purpose.

    ``dataclasses.asdict()`` would turn ``inner`` into a plain dict, so a
    response model expecting a typed nested object would receive an anonymous
    one — and ``Money`` would silently flatten into ``{amount_minor, currency}``.
    Routers map nested lists explicitly instead.
    """
    result = dto_dict(Slotted(name="villa", secret_key="k", inner=Inner(7)))
    assert isinstance(result["inner"], Inner)
    assert result["inner"].value == 7


def test_refuses_a_non_dataclass() -> None:
    with pytest.raises(TypeError, match="dataclass instance"):
        dto_dict({"name": "villa"})
    with pytest.raises(TypeError, match="dataclass instance"):
        dto_dict(Slotted)  # the class, not an instance


def test_no_router_uses_vars() -> None:
    """A guard against the whole class of bug, not just the instances fixed.

    ``vars()`` reads correctly in review and fails at runtime on every DTO we
    have. Grepping is a blunt instrument and exactly right here: the rule is
    simple, the failure mode is severe, and a new router is the most likely
    place for it to reappear.
    """
    offenders = [
        f"{path.relative_to(Path('src'))}:{i}"
        for path in Path("src/app").rglob("*.py")
        # serialization.py names `vars()` in its own docstring, explaining why
        # not to use it.
        if path.name != "serialization.py"
        for i, line in enumerate(path.read_text().splitlines(), 1)
        if re.search(r"(?<![\w.])vars\(", line) and not line.lstrip().startswith(("#", "*"))
    ]
    assert offenders == [], (
        "vars() raises TypeError on a slots=True dataclass, and every DTO here is "
        f"slotted. Use core.serialization.dto_dict instead. Found: {offenders}"
    )
