"""Declarative base and naming conventions.

The naming convention is the load-bearing part. Postgres auto-generates names
like ``bookings_check1``; you cannot reliably ``DROP CONSTRAINT`` something
whose name depends on creation order, and an on-call engineer reading
``violates check constraint "bookings_check7"`` learns nothing.
``ck_bookings_no_overbook`` tells them everything.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def __repr__(self) -> str:  # pragma: no cover
        pk: Any = getattr(self, "id", None)
        return f"<{type(self).__name__} id={pk}>"
