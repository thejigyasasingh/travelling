"""Cursor pagination."""

from __future__ import annotations

import pytest

from app.core.types.pagination import (
    MAX_PAGE_SIZE,
    Cursor,
    InvalidCursorError,
    Page,
    PageRequest,
)

pytestmark = pytest.mark.unit


class TestCursor:
    def test_roundtrip(self) -> None:
        cursor = Cursor(("2026-09-05T10:00:00", "9f3a-uuid"))
        assert Cursor.decode(cursor.encode()).values == cursor.values

    def test_encoding_is_url_safe(self) -> None:
        # Cursors travel in query strings; +, / and = would need escaping.
        encoded = Cursor((1, 2, 3)).encode()
        assert not set(encoded) & {"+", "/", "="}

    @pytest.mark.parametrize("bad", ["", "!!!", "notbase64", "YWJj"])
    def test_malformed_cursor_raises_a_typed_error(self, bad: str) -> None:
        # Must surface as a 422, never a 500 — clients send stale cursors all
        # the time, and a bookmarked URL should not page someone.
        with pytest.raises(InvalidCursorError):
            Cursor.decode(bad)


class TestPageRequest:
    def test_over_fetches_by_one_to_detect_a_next_page(self) -> None:
        # Avoids a second COUNT(*) over the same predicate just to answer
        # "is there more?".
        assert PageRequest(limit=20).fetch_limit == 21

    def test_rejects_oversized_limit(self) -> None:
        with pytest.raises(ValueError, match="limit must be"):
            PageRequest(limit=MAX_PAGE_SIZE + 1)

    def test_rejects_zero_limit(self) -> None:
        with pytest.raises(ValueError, match="limit must be"):
            PageRequest(limit=0)


class TestPage:
    def test_sentinel_row_is_trimmed(self) -> None:
        request = PageRequest(limit=3)
        page = Page.from_overfetch([1, 2, 3, 4], request, cursor_of=lambda x: (x,))
        assert page.items == [1, 2, 3]
        assert page.has_more

    def test_last_page_has_no_cursor(self) -> None:
        page = Page.from_overfetch([1, 2], PageRequest(limit=3), cursor_of=lambda x: (x,))
        assert page.items == [1, 2]
        assert not page.has_more

    def test_empty_page(self) -> None:
        page = Page.from_overfetch([], PageRequest(limit=3), cursor_of=lambda x: (x,))
        assert page.items == []
        assert not page.has_more

    def test_map_preserves_the_cursor(self) -> None:
        page = Page.from_overfetch([1, 2, 3, 4], PageRequest(limit=3), cursor_of=lambda x: (x,))
        mapped = page.map(str)
        assert mapped.items == ["1", "2", "3"]
        assert mapped.next_cursor == page.next_cursor
