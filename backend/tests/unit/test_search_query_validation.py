"""Enum query parameters must be validated at the boundary.

Taking `sort` as a `str` and calling `SearchSort(value)` inside the handler
raised a `ValueError` that escaped to the ASGI layer — where **no response is
ever written**. The client waited until it timed out, and enough such requests
exhausted the worker: an unauthenticated denial of service reachable from a
URL, triggered by a value two of our own clients were sending.

The fix is a typed parameter, so FastAPI answers 422 before the handler runs.
These tests pin the contract from both directions: the accepted values are
exactly what the clients send, and an unknown value is a refusal rather than a
hang.
"""

from __future__ import annotations

from typing import get_args, get_origin, get_type_hints

import pytest

from app.modules.property.application.dto import SearchSort
from app.modules.property.domain.value_objects import CancellationPolicy, PropertyType
from app.modules.property.interface.router import search

pytestmark = pytest.mark.unit


def _annotation(name: str) -> object:
    """Resolve the real type.

    The router uses `from __future__ import annotations`, so every annotation
    is a string until something evaluates it — `get_type_hints` is that
    something, and `include_extras` keeps the `Annotated[...]` wrapper FastAPI
    reads.
    """
    return get_type_hints(search, include_extras=True)[name]


def test_sort_is_typed_as_the_enum_not_a_string() -> None:
    """A `str` here is the bug: it defers validation into the handler body."""
    assert _annotation("sort") is SearchSort


@pytest.mark.parametrize(
    ("name", "member"),
    [("property_type", PropertyType), ("cancellation", CancellationPolicy)],
)
def test_list_enum_parameters_are_typed(name: str, member: type) -> None:
    annotation = _annotation(name)
    # Annotated[list[Enum] | None, Query()] — dig out the list's element type.
    inner = get_args(annotation)[0]
    list_type = next(arg for arg in get_args(inner) if get_origin(arg) is list)
    assert get_args(list_type)[0] is member


def test_the_sort_values_are_exactly_what_the_clients_send() -> None:
    """The web and Flutter clients both hard-code these strings.

    They previously sent `rating` and `distance`, which this enum does not
    have — so the home screen's "top rated" strip was silently empty on both,
    and each request wedged a connection.
    """
    assert {s.value for s in SearchSort} == {
        "relevance",
        "price_asc",
        "price_desc",
        "rating_desc",
        "distance_asc",
        "newest",
    }


def test_an_unknown_sort_value_is_refused_by_the_enum() -> None:
    for bad in ("rating", "distance", "", "; DROP TABLE properties"):
        with pytest.raises(ValueError, match="not a valid SearchSort"):
            SearchSort(bad)
