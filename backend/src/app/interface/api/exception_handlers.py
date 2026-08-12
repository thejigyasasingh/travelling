"""Exception → HTTP translation. The only place in the codebase that does it.

The rules this enforces:

**No handler ever raises ``HTTPException``.** Domain and application code raise
domain errors; this module decides what they mean over HTTP. That is what lets
the same use case back an HTTP endpoint, a Celery task and a CLI command.

**Internal details never reach a client.** A 500 returns a generic message and
the ``request_id``. Stack traces, SQL fragments and constraint names in an API
response are a free schema disclosure — ``duplicate key value violates unique
constraint "uq_users_email"`` tells an attacker the table, the column and that
the account exists.

**The log carries what the response does not.** Full traceback, the constraint
that fired, the SQLSTATE. The user gets an ID; the engineer gets everything.

**Log level follows the taxonomy, not the status code.** A 404 is INFO — users
request missing things constantly. A 500 is ERROR and pages someone. Logging
every 4xx at ERROR is how alert fatigue starts.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import (
    HTTP_409_CONFLICT,
    HTTP_413_CONTENT_TOO_LARGE,
    HTTP_422_UNPROCESSABLE_CONTENT,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.core.types.pagination import InvalidCursorError
from app.interface.api.middleware.body_limit import BodyTooLargeError
from app.shared.domain.errors import (
    BusinessRuleViolationError,
    ConcurrencyError,
    DomainError,
    EntityNotFoundError,
    InvariantError,
)

logger = get_logger(__name__)

DOC_BASE = "https://docs.roamingwandering.com/errors"


def _envelope(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "request_id": getattr(request.state, "request_id", None),
                "doc_url": f"{DOC_BASE}/{code.lower()}",
            }
        },
    )


def register_exception_handlers(app: FastAPI, settings: Settings) -> None:
    expose_internals = not settings.app_env.is_deployed

    # ── our own taxonomy ──────────────────────────────────────────────────

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> ORJSONResponse:
        log = getattr(logger, exc.log_level, logger.error)
        log(
            "app_error",
            code=exc.code,
            status=exc.status_code,
            path=request.url.path,
            detail=exc.message,
        )
        return _envelope(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
            headers=exc.headers or None,
        )

    # ── domain errors ─────────────────────────────────────────────────────

    @app.exception_handler(DomainError)
    async def _domain_error(request: Request, exc: DomainError) -> ORJSONResponse:
        """Maps business outcomes onto status codes.

        The mapping lives here rather than on the exception because the domain
        must not know HTTP exists — the same error becomes an exit code in the
        CLI and a retry decision in a Celery task. The one exception is an error
        that declares its own ``status_code``, which a module uses to say
        something the generic table cannot; see ``_resolve_domain_status``.
        """
        status, level = _resolve_domain_status(exc)

        if isinstance(exc, InvariantError):
            # Our bug, not the user's. Page someone, and say nothing useful to
            # the client.
            logger.error("invariant_violated", path=request.url.path, detail=exc.message)
            return _envelope(
                request,
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                code=ErrorCode.INTERNAL_ERROR,
                message="An unexpected error occurred.",
            )

        getattr(logger, level)("domain_error", code=exc.code, path=request.url.path)
        return _envelope(
            request, status_code=status, code=exc.code, message=exc.message, details=exc.details
        )

    # ── validation ────────────────────────────────────────────────────────

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> ORJSONResponse:
        """Flattens pydantic's ``loc`` tuples into dotted paths.

        The default FastAPI 422 body is pydantic's internal structure. Clients
        end up writing a parser for it, which then breaks on a pydantic
        upgrade. A flat ``[{field, message, code}]`` is ours to keep stable.
        """
        fields = [
            {
                "field": ".".join(str(p) for p in err["loc"][1:]) or str(err["loc"][0]),
                "message": err["msg"],
                "code": err["type"],
            }
            for err in exc.errors()
        ]
        logger.info(
            "request_validation_failed",
            path=request.url.path,
            fields=[f["field"] for f in fields],  # names only — values may be PII
        )
        return _envelope(
            request,
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            code=ErrorCode.VALIDATION_ERROR,
            message="The request failed validation.",
            details={"fields": fields},
        )

    @app.exception_handler(PydanticValidationError)
    async def _pydantic(request: Request, exc: PydanticValidationError) -> ORJSONResponse:
        """A pydantic error escaping *outside* request parsing means a
        response model or an internal DTO failed to build — our bug, not the
        client's, so it is a 500."""
        logger.error("internal_validation_error", path=request.url.path, errors=exc.error_count())
        return _envelope(
            request,
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred.",
        )

    @app.exception_handler(InvalidCursorError)
    async def _bad_cursor(request: Request, exc: InvalidCursorError) -> ORJSONResponse:
        return _envelope(
            request,
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            code=ErrorCode.VALIDATION_ERROR,
            message="Invalid pagination cursor.",
        )

    # ── body limit ────────────────────────────────────────────────────────

    @app.exception_handler(BodyTooLargeError)
    async def _too_large(request: Request, exc: BodyTooLargeError) -> ORJSONResponse:
        return _envelope(
            request,
            status_code=HTTP_413_CONTENT_TOO_LARGE,
            code=ErrorCode.PAYLOAD_TOO_LARGE,
            message="Request body is too large.",
            details={"max_bytes": exc.limit},
        )

    # ── database ──────────────────────────────────────────────────────────

    @app.exception_handler(IntegrityError)
    async def _integrity(request: Request, exc: IntegrityError) -> ORJSONResponse:
        """A constraint fired. Almost always a genuine conflict — a duplicate
        email, an overlapping booking — reached through a race that the
        application-level check could not see.

        The constraint *name* is logged and never returned: it names the table
        and the columns.

        The driver's own message is logged beside it. Not every violation has a
        name — a NOT NULL has none — and ``constraint=None`` on its own says
        only that something failed, which is not enough to fix it at 3am.
        """
        constraint = _constraint_name(exc)
        logger.warning(
            "integrity_error",
            path=request.url.path,
            constraint=constraint,
            # str(exc.orig) is the driver's message, which carries the column
            # for the unnamed violations. Log-only: it names internals.
            db_error=str(exc.orig) if exc.orig is not None else None,
        )
        return _envelope(
            request,
            status_code=HTTP_409_CONFLICT,
            code=ErrorCode.CONFLICT,
            message="The request conflicts with existing data.",
            details={"constraint": constraint} if expose_internals else {},
        )

    @app.exception_handler(StaleDataError)
    async def _stale(request: Request, exc: StaleDataError) -> ORJSONResponse:
        """Optimistic lock lost: someone else updated the row first.

        A conflict, not a fault — two support agents on the same payment, or a
        guest double-clicking refund. Without this it reaches the catch-all and
        answers 500, which tells the client to report a bug rather than retry.

        Retrying is safe precisely because the losing transaction rolled back
        *whole*: nothing it wrote was kept.
        """
        logger.warning("stale_data", path=request.url.path)
        return _envelope(
            request,
            status_code=HTTP_409_CONFLICT,
            code=ErrorCode.CONFLICT,
            message="This record was modified by someone else. Please retry.",
        )

    @app.exception_handler(OperationalError)
    async def _operational(request: Request, exc: OperationalError) -> ORJSONResponse:
        """Connection lost, pool exhausted, statement timeout. Transient by
        nature, so the client is told to retry rather than shown an error."""
        logger.error("database_unavailable", path=request.url.path, error=str(exc.orig)[:200])
        return _envelope(
            request,
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message="The service is temporarily unavailable. Please retry.",
            headers={"Retry-After": "5"},
        )

    @app.exception_handler(DBAPIError)
    async def _dbapi(request: Request, exc: DBAPIError) -> ORJSONResponse:
        logger.error("database_error", path=request.url.path, error=str(exc.orig)[:200])
        return _envelope(
            request,
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred.",
        )

    # ── framework + catch-all ─────────────────────────────────────────────

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> ORJSONResponse:
        """Reshapes framework 404s/405s into our envelope, so a client never
        has to handle two different error formats."""
        code = {404: ErrorCode.NOT_FOUND, 405: "METHOD_NOT_ALLOWED"}.get(
            exc.status_code, f"HTTP_{exc.status_code}"
        )
        return _envelope(
            request,
            status_code=exc.status_code,
            code=code,
            message=str(exc.detail),
            headers=dict(exc.headers) if exc.headers else None,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> ORJSONResponse:
        """The last line of defence. Anything reaching here is a bug.

        ``exc_info=True`` sends the full traceback to the log (and to Sentry);
        the client gets a generic message plus the request id, which is enough
        for support to find the traceback without leaking it.
        """
        logger.exception(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error_type=type(exc).__name__,
        )
        return _envelope(
            request,
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred.",
            details={"debug": f"{type(exc).__name__}: {exc}"} if expose_internals else {},
        )


_DOMAIN_STATUS: dict[type[DomainError], tuple[int, str]] = {
    EntityNotFoundError: (404, "info"),
    BusinessRuleViolationError: (409, "info"),
    ConcurrencyError: (409, "info"),
}


def _resolve_domain_status(exc: DomainError) -> tuple[int, str]:
    """Status and log level for a domain error.

    Resolution order, and why it is this order:

    1. **An explicit ``status_code`` on the error.** A module uses this to say
       what the generic table cannot — "this is a 404 so the endpoint is not an
       enumeration oracle", "this is a 503 because the gateway is down and the
       client should retry".
    2. **The table, walked up the MRO.** An exact-type lookup silently missed
       every subclass, so a ``DatesUnavailableError`` — a
       ``BusinessRuleViolationError`` — reached the default rather than its
       mapping. That happened to give the same 409, which is exactly why it
       went unnoticed; an ``EntityNotFoundError`` subclass would have answered
       409 instead of 404.
    3. **409.** A business rule refused; nothing about the request was
       malformed and nothing is missing.
    """
    declared = getattr(exc, "status_code", None)
    if isinstance(declared, int):
        # 5xx is our problem, not the caller's, so it is logged accordingly.
        return declared, ("error" if declared >= 500 else "info")

    for base in type(exc).__mro__:
        mapped = _DOMAIN_STATUS.get(base)
        if mapped is not None:
            return mapped

    return HTTP_409_CONFLICT, "info"


def _constraint_name(exc: IntegrityError) -> str | None:
    """asyncpg exposes it as ``constraint_name``; psycopg via ``diag``."""
    orig = exc.orig
    for attr in ("constraint_name", "constraint"):
        if (value := getattr(orig, attr, None)) is not None:
            return str(value)
    diag = getattr(orig, "diag", None)
    return str(getattr(diag, "constraint_name", "")) or None
