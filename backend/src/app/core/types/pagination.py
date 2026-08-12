"""Pagination primitives.

Two strategies, chosen per endpoint rather than one imposed everywhere:

**Cursor** — the default for anything a user scrolls (search results, reviews,
messages, bookings). ``OFFSET 40000`` makes Postgres walk and discard 40,000
rows; at a million listings the last page of a search is a table scan. A cursor
is a ``WHERE (sort_key, id) < (...)`` predicate that rides an index, so page
1,000 costs the same as page 1. It is also stable: new rows arriving mid-scroll
do not shift items across page boundaries and cause duplicates.

**Offset** — admin tables and exports only, where a human wants "page 7 of 20"
and the row count is small and bounded.

Cursors are opaque base64 to clients. Not for security — the contents are
signed by nothing and readable by anyone — but so the encoding can change
without breaking a shipped mobile app that stored one.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, field
from typing import Any, Self

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class InvalidCursorError(ValueError):
    """Malformed or tampered cursor. Surfaces as a 422, never a 500."""


@dataclass(frozen=True, slots=True)
class Cursor:
    """Position in a stable sort. ``values`` mirrors the ORDER BY tuple, whose
    last element is always a unique tiebreaker (the row id) — without it, rows
    sharing a sort key are skipped or repeated across pages."""

    values: tuple[Any, ...]

    def encode(self) -> str:
        raw = json.dumps({"v": list(self.values)}, separators=(",", ":"), default=str)
        return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")

    @classmethod
    def decode(cls, token: str) -> Self:
        try:
            padded = token + "=" * (-len(token) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded))
            return cls(tuple(payload["v"]))
        except (binascii.Error, ValueError, KeyError, TypeError) as exc:
            raise InvalidCursorError("Malformed pagination cursor") from exc


@dataclass(frozen=True, slots=True)
class PageRequest:
    limit: int = DEFAULT_PAGE_SIZE
    cursor: Cursor | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= MAX_PAGE_SIZE:
            msg = f"limit must be between 1 and {MAX_PAGE_SIZE}"
            raise ValueError(msg)

    @property
    def fetch_limit(self) -> int:
        """Over-fetch by one row to learn whether a next page exists without
        a second ``COUNT(*)`` query over the same predicate."""
        return self.limit + 1


@dataclass(frozen=True, slots=True)
class Page[T]:
    items: list[T]
    next_cursor: Cursor | None = None
    # Deliberately optional. An exact total on a filtered search over a million
    # listings is a full index scan on every keystroke; the UI shows "200+"
    # instead. Set it only where the count is cheap and genuinely needed.
    total: int | None = None

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None

    @classmethod
    def from_overfetch(cls, rows: list[T], request: PageRequest, cursor_of: Any = None) -> Page[T]:
        """Trim the sentinel row and derive the next cursor from the last
        surviving item."""
        has_more = len(rows) > request.limit
        items = rows[: request.limit]
        next_cursor = Cursor(cursor_of(items[-1])) if (has_more and items and cursor_of) else None
        return cls(items=items, next_cursor=next_cursor)

    def map(self, fn: Any) -> Page[Any]:
        """Convert entities to DTOs while keeping the cursor intact."""
        return Page(
            items=[fn(i) for i in self.items], next_cursor=self.next_cursor, total=self.total
        )


@dataclass(frozen=True, slots=True)
class OffsetPage[T]:
    """Admin-only. See the module docstring for why this is not the default."""

    items: list[T]
    total: int
    page: int = 1
    size: int = DEFAULT_PAGE_SIZE
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def pages(self) -> int:
        return max(1, -(-self.total // self.size))
