"""Support inputs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OpenTicketInput:
    subject: str
    body: str
    category: str
    requester_name: str
    requester_email: str
    booking_id: uuid.UUID | None = None
