"""Structured logging.

Two things matter here and nothing else does:

1. **Correlation.** Every line carries ``request_id``/``trace_id`` bound from a
   ``contextvar``, so one query reconstructs a request across the API, three
   Celery workers and two outbound calls. Without propagation you have
   fragments and guesswork.

2. **PII never reaches a log sink.** Redaction is a processor at the emit
   boundary, not a rule engineers follow. Everyone eventually logs a whole
   request body while debugging; the processor makes that harmless rather than
   a 90-day-retained credential leak.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import Settings

# ── Request-scoped context ────────────────────────────────────────────────
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)

# ── PII policy ────────────────────────────────────────────────────────────
REDACT_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "current_password",
        "new_password",
        "token",
        "access_token",
        "refresh_token",
        "refresh_token_hash",
        "id_token",
        "client_secret",
        "authorization",
        "cookie",
        "set-cookie",
        "api_key",
        "secret",
        "private_key",
        "card_number",
        "pan",
        "cvv",
        "cvc",
        "otp",
        "bank_account",
        "account_number",
        "ifsc",
        "id_document",
        "doc_number",
        "aadhaar",
    }
)
MASK_KEYS = frozenset({"email", "phone", "phone_e164", "requester_email", "destination"})

_REDACTED = "[REDACTED]"
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_MAX_DEPTH = 6


def _mask_email(value: str) -> str:
    local, _, domain = value.partition("@")
    if not domain:
        return _REDACTED
    head = local[0] if local else ""
    return f"{head}{'*' * max(len(local) - 1, 1)}@{domain}"


def _mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return f"***{digits[-4:]}" if len(digits) >= 4 else _REDACTED


def _mask(key: str, value: str) -> str:
    return _mask_email(value) if "email" in key else _mask_phone(value)


def _scrub_value(value: Any, depth: int) -> Any:
    if depth > _MAX_DEPTH:
        return "[TRUNCATED]"
    if isinstance(value, MutableMapping):
        return _scrub_mapping(value, depth + 1)
    if isinstance(value, (list, tuple, set)):
        return type(value)(_scrub_value(v, depth + 1) for v in value)
    if isinstance(value, str):
        value = _CARD_RE.sub(_REDACTED, value)
        return _JWT_RE.sub(_REDACTED, value)
    return value


def _scrub_mapping(data: MutableMapping[str, Any], depth: int = 0) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        lowered = key.lower()
        if lowered in REDACT_KEYS:
            out[key] = _REDACTED
        elif lowered in MASK_KEYS and isinstance(value, str):
            out[key] = _mask(lowered, value)
        else:
            out[key] = _scrub_value(value, depth)
    return out


def scrub_pii(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """Terminal safety net. Runs on every event, in every environment."""
    return _scrub_mapping(event_dict)


def bind_request_context(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """Attach correlation IDs without every call site passing them."""
    if (rid := request_id_var.get()) is not None:
        event_dict.setdefault("request_id", rid)
    if (tid := trace_id_var.get()) is not None:
        event_dict.setdefault("trace_id", tid)
    if (uid := user_id_var.get()) is not None:
        event_dict.setdefault("user_id", uid)
    return event_dict


def drop_color_message(_logger: Any, _method: str, event_dict: EventDict) -> EventDict:
    """uvicorn duplicates `event` into `color_message`; it is pure noise in JSON."""
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Idempotent. Called from the app lifespan and from the Celery bootstrap."""
    json_output = settings.log_format == "json"

    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        bind_request_context,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        drop_color_message,
        scrub_pii,  # LAST before rendering — nothing may add PII after it
    ]

    structlog.configure(
        processors=[
            *shared,
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        # Human-readable locally. This is the ONLY reason console mode exists;
        # nobody reads logs at 3k RPS, they query them.
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # Route third-party loggers through the same pipeline so their output is
    # also scrubbed and correlated.
    for name, level in (
        ("uvicorn", logging.INFO),
        ("uvicorn.error", logging.INFO),
        ("uvicorn.access", logging.WARNING),  # our own middleware logs access
        ("sqlalchemy.engine", logging.WARNING),
        ("celery", logging.INFO),
        ("httpx", logging.WARNING),
    ):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
        lg.setLevel(level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)
