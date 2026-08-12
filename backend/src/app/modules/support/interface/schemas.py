"""Support HTTP schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OpenTicketRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=10, max_length=5000)
    category: Literal[
        "booking", "payment", "refund", "property", "account", "check_in", "other"
    ] = "other"
    booking_id: uuid.UUID | None = None
    #: Only used when the requester has no account — the signed-in case takes
    #: these from the token, which cannot be spoofed.
    requester_name: str | None = Field(default=None, max_length=120)
    requester_email: str | None = Field(default=None, max_length=320)


class ReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    #: Staff only, and ignored for anyone else. An internal note is never
    #: rendered to the requester.
    internal: bool = False


class ResolveRequest(BaseModel):
    resolution: str = Field(min_length=3, max_length=2000)


class AssignRequest(BaseModel):
    agent_id: uuid.UUID


class SetPriorityRequest(BaseModel):
    priority: Literal["urgent", "high", "normal", "low"]


class TicketMessageResponse(BaseModel):
    id: uuid.UUID
    author_name: str
    body: str
    is_internal: bool
    sent_at: datetime


class TicketResponse(BaseModel):
    id: uuid.UUID
    reference: str
    subject: str
    category: str
    priority: str
    status: str
    requester_name: str
    requester_email: str
    booking_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    opened_at: datetime
    first_responded_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution: str | None = None
    #: When a first reply becomes late, so the queue can show what is at risk.
    response_due_at: datetime
    is_breaching: bool
    messages: list[TicketMessageResponse] = Field(default_factory=list)


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    page: int
    size: int


class TicketCountsResponse(BaseModel):
    counts: dict[str, int]
