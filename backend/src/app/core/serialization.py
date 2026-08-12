"""Turning a DTO into keyword arguments for a response model.

``vars(obj)`` returns ``obj.__dict__`` — and a ``@dataclass(slots=True)`` has no
``__dict__``, so it raises ``TypeError``. Every DTO in this codebase is slotted
(they are created per request, and slots make that meaningfully cheaper), so
``vars()`` is never the right tool here even though it reads like it is.

``dataclasses.asdict()`` is not the right tool either: it deep-copies and
recursively converts *nested* dataclasses into dicts, so a ``PaymentView``
would arrive with its refunds turned into anonymous dicts and its ``Money``
fields flattened. Response models expect the nested objects intact.

So: a shallow field read. One level, no copying, no recursion.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any


def dto_dict(obj: Any, *, exclude: frozenset[str] = frozenset()) -> dict[str, Any]:
    """Shallow ``{field: value}`` for a dataclass, slotted or not.

    ``exclude`` drops fields that are internal to the application layer and must
    not reach the wire — a storage key that the interface turns into a signed
    URL, for instance.
    """
    if not is_dataclass(obj) or isinstance(obj, type):
        msg = f"dto_dict expects a dataclass instance, got {type(obj).__name__}"
        raise TypeError(msg)
    return {f.name: getattr(obj, f.name) for f in fields(obj) if f.name not in exclude}
