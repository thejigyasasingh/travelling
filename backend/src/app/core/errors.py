"""Error taxonomy.

The wire contract is one shape, always::

    {"error": {"code", "message", "details", "request_id", "doc_url"}}

``code`` is a **stable machine contract** clients switch on. ``message`` is
human-facing, localisable, and may change freely. Conflating them — clients
parsing error strings — creates a contract you can never change.

Domain code raises these; it never imports ``fastapi.HTTPException``. The
translation to HTTP happens once, in the exception handlers.
"""

from __future__ import annotations

from typing import Any


class ErrorCode:
    """Stable codes. Add freely; never rename or repurpose one — a shipped
    mobile client may be switching on it for years."""

    # generic
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"

    # auth
    UNAUTHENTICATED = "UNAUTHENTICATED"
    # The S105 suppressions below: these are error-code strings, not secrets.
    TOKEN_EXPIRED = "TOKEN_EXPIRED"  # noqa: S105
    TOKEN_INVALID = "TOKEN_INVALID"  # noqa: S105
    TOKEN_REUSE_DETECTED = "TOKEN_REUSE_DETECTED"  # noqa: S105
    FORBIDDEN = "FORBIDDEN"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"

    # idempotency
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    IDEMPOTENT_REQUEST_IN_PROGRESS = "IDEMPOTENT_REQUEST_IN_PROGRESS"

    # domain (populated as modules land)
    BOOKING_DATES_UNAVAILABLE = "BOOKING_DATES_UNAVAILABLE"
    BOOKING_PRICE_CHANGED = "BOOKING_PRICE_CHANGED"
    PAYMENT_FAILED = "PAYMENT_FAILED"


class AppError(Exception):
    """Base for everything the application raises deliberately.

    ``status_code`` lives on the exception rather than in a handler-side
    mapping table so a new error type cannot be added without deciding what it
    means over HTTP.
    """

    status_code: int = 500
    code: str = ErrorCode.INTERNAL_ERROR
    message: str = "An unexpected error occurred."
    log_level: str = "error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        self.headers = headers or {}
        super().__init__(self.message)

    def __repr__(self) -> str:  # pragma: no cover
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


# ── 4xx ───────────────────────────────────────────────────────────────────


class ValidationError(AppError):
    status_code = 422
    code = ErrorCode.VALIDATION_ERROR
    message = "The request failed validation."
    log_level = "info"


class NotFoundError(AppError):
    """Also raised for resources the actor may not see.

    Returning 403 for another user's booking confirms it exists, which turns
    ID enumeration into an oracle. Where existence itself is private, 404 is
    the correct answer.
    """

    status_code = 404
    code = ErrorCode.NOT_FOUND
    message = "Resource not found."
    log_level = "info"


class ConflictError(AppError):
    status_code = 409
    code = ErrorCode.CONFLICT
    message = "The request conflicts with the current state."
    log_level = "info"


class UnauthenticatedError(AppError):
    status_code = 401
    code = ErrorCode.UNAUTHENTICATED
    message = "Authentication required."
    log_level = "info"

    def __init__(self, message: str | None = None, **kw: Any) -> None:
        super().__init__(message, **kw)
        self.headers.setdefault("WWW-Authenticate", "Bearer")


class TokenExpiredError(UnauthenticatedError):
    code = ErrorCode.TOKEN_EXPIRED
    message = "Access token has expired."


class TokenInvalidError(UnauthenticatedError):
    code = ErrorCode.TOKEN_INVALID
    message = "Access token is invalid."


class TokenReuseDetectedError(UnauthenticatedError):
    """Refresh-token reuse. The whole family is revoked; the user must
    re-authenticate. Logged at WARNING because it is a security signal."""

    code = ErrorCode.TOKEN_REUSE_DETECTED
    message = "Session ended due to suspicious activity. Please sign in again."
    log_level = "warning"


class ForbiddenError(AppError):
    status_code = 403
    code = ErrorCode.FORBIDDEN
    message = "You do not have permission to perform this action."
    log_level = "info"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = ErrorCode.PAYLOAD_TOO_LARGE
    message = "Request body is too large."
    log_level = "info"


class RateLimitedError(AppError):
    status_code = 429
    code = ErrorCode.RATE_LIMITED
    message = "Too many requests. Please slow down."
    log_level = "info"

    def __init__(self, retry_after: int, **kw: Any) -> None:
        super().__init__(**kw)
        self.headers.setdefault("Retry-After", str(retry_after))
        self.details.setdefault("retry_after_seconds", retry_after)


class IdempotencyConflictError(ConflictError):
    code = ErrorCode.IDEMPOTENCY_KEY_REUSED
    message = "This idempotency key was already used with a different request body."


class IdempotentRequestInProgressError(ConflictError):
    code = ErrorCode.IDEMPOTENT_REQUEST_IN_PROGRESS
    message = "An identical request is already being processed."


# ── 5xx ───────────────────────────────────────────────────────────────────


class InternalError(AppError):
    status_code = 500
    code = ErrorCode.INTERNAL_ERROR


class DependencyUnavailableError(AppError):
    """An upstream we do not control failed, or its circuit is open.

    Distinct from ``InternalError`` because it is not our bug, it is usually
    transient, and clients should retry rather than report it.
    """

    status_code = 503
    code = ErrorCode.DEPENDENCY_UNAVAILABLE
    message = "A required service is temporarily unavailable."
    log_level = "warning"

    def __init__(self, dependency: str, **kw: Any) -> None:
        super().__init__(**kw)
        self.details.setdefault("dependency", dependency)
        self.headers.setdefault("Retry-After", "10")
