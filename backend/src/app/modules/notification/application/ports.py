"""What the use case needs from the outside world.

Two ports, and the split matters: **the log is written even when the transport
is not called.** A suppressed message and a failed one are both rows; only a
sent one touched SMTP. Keeping the record separate from the transport is what
makes "we never tried to send this, and here is why" an answerable question.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Protocol


class EmailSender(Protocol):
    """Delivery. Returns the provider's message id when it offers one.

    Raises on failure rather than returning a status: a caller that has to
    remember to check a boolean will eventually forget, and the failure is
    silent when it does.
    """

    async def send(
        self,
        *,
        to: str,
        subject: str,
        text: str,
        html: str,
    ) -> str | None: ...


class NotificationLog(Protocol):
    """The `notifications` table.

    `claim` is the idempotency primitive. It inserts a `queued` row and returns
    None if `dedupe_key` is already taken — so two concurrent workers handling
    the same redelivered event resolve to one message rather than two, decided
    by a unique index rather than by a read-then-write race.
    """

    async def claim(
        self,
        *,
        channel: str,
        template: str,
        recipient: str,
        user_id: uuid.UUID | None,
        context: dict[str, Any],
        dedupe_key: str,
        now: datetime,
    ) -> uuid.UUID | None: ...

    async def mark_sent(
        self,
        notification_id: uuid.UUID,
        *,
        subject: str,
        preview: str,
        provider_message_id: str | None,
        now: datetime,
    ) -> None: ...

    async def mark_failed(
        self, notification_id: uuid.UUID, *, error: str, now: datetime
    ) -> None: ...

    async def mark_suppressed(
        self, notification_id: uuid.UUID, *, reason: str, now: datetime
    ) -> None: ...
