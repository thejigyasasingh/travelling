"""Framework-free primitives shared by every layer, including the domain.

Nothing here may import fastapi, sqlalchemy or pydantic — the domain-purity
contract in ``.importlinter`` depends on that staying true.
"""

from app.core.types.date_range import DateRange
from app.core.types.money import Money, sum_money
from app.core.types.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    Cursor,
    InvalidCursorError,
    OffsetPage,
    Page,
    PageRequest,
)

__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "Cursor",
    "DateRange",
    "InvalidCursorError",
    "Money",
    "OffsetPage",
    "Page",
    "PageRequest",
    "sum_money",
]
