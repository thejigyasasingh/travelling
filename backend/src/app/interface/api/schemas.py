"""Wire schemas shared by every endpoint.

**Errors have one shape, forever.** A client should be able to write one error
handler, not one per endpoint. ``code`` is the machine contract; ``message`` is
for humans and may change.

**Successful list responses are enveloped, single resources are not.** A list
needs pagination metadata that has nowhere else to live. A single resource does
not, and wrapping it in ``{"data": {...}}`` just makes every client type an
extra layer for no information.

**``request_id`` is on every error.** A user can paste it into a support
ticket, and one query produces the whole request. It is the single cheapest
thing you can do for supportability.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    code: str = Field(description="Stable machine-readable code. Switch on this.")
    message: str = Field(description="Human-readable. May change; do not parse.")
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = Field(default=None, description="Quote this in support tickets.")
    doc_url: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "BOOKING_DATES_UNAVAILABLE",
                "message": "Those dates are no longer available.",
                "details": {"available_from": "2026-09-12"},
                "request_id": "8f14e45fceea167a5a36dedd4bea2543",
            }
        }
    )


class ErrorResponse(BaseModel):
    error: ErrorDetail


class FieldError(BaseModel):
    """One validation failure. ``field`` is a dotted path
    (``guests.0.age``) so a client can attach the message to the right input
    without parsing pydantic's ``loc`` tuples."""

    field: str
    message: str
    code: str


class PageMeta(BaseModel):
    next_cursor: str | None = None
    has_more: bool = False
    #: Absent by default — see ``core/types/pagination.py`` for why an exact
    #: count is not free.
    total: int | None = None


class PagedResponse[T](BaseModel):
    items: list[T]
    meta: PageMeta


class HealthStatus(BaseModel):
    status: str
    version: str
    environment: str
    checks: dict[str, dict[str, Any]] = Field(default_factory=dict)


class AcceptedResponse(BaseModel):
    """202 for work that continues after the response.

    Returning 200 for an async operation is a lie the client cannot detect;
    202 plus a poll URL is honest and lets the client show real progress.
    """

    accepted: bool = True
    job_id: str | None = None
    poll_url: str | None = None
