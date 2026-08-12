"""Review inputs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ReviewDraft:
    """What a guest submits.

    `booking_id` rather than `property_id`: the booking is the evidence, and
    taking a property id would let anyone review anything.
    """

    booking_id: uuid.UUID
    rating: int
    body: str
    title: str | None = None
    categories: dict[str, int] = field(default_factory=dict)
