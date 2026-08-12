"""The notification log, over the `notifications` table."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SqlNotificationLog:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
    ) -> uuid.UUID | None:
        """Insert a queued row, or return None if this message is already taken.

        `ON CONFLICT DO NOTHING` on `uq_notifications_dedupe` is the entire
        once-only guarantee. Two workers handling the same redelivered event
        both run this; Postgres picks one, the other gets no row back and
        stops. A `SELECT` followed by an `INSERT` would have a window between
        them wide enough to send a guest two confirmations.
        """
        row = (
            await self._session.execute(
                text(
                    """
                    INSERT INTO notifications
                        (id, channel, template, user_id, recipient, context,
                         status, attempts, dedupe_key, created_at)
                    VALUES
                        (gen_random_uuid(), :channel, :template, :user_id, :recipient,
                         CAST(:context AS jsonb), 'queued', 1, :dedupe_key, :now)
                    ON CONFLICT ON CONSTRAINT uq_notifications_dedupe DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "channel": channel,
                    "template": template,
                    "user_id": user_id,
                    "recipient": recipient,
                    # Serialised here rather than relying on the driver: this
                    # runs through `text()` for the ON CONFLICT clause, so
                    # there is no ORM type to do the conversion.
                    "context": _json(context),
                    "dedupe_key": dedupe_key,
                    "now": now,
                },
            )
        ).first()
        return None if row is None else uuid.UUID(str(row[0]))

    async def mark_sent(
        self,
        notification_id: uuid.UUID,
        *,
        subject: str,
        preview: str,
        provider_message_id: str | None,
        now: datetime,
    ) -> None:
        await self._session.execute(
            text(
                """
                UPDATE notifications
                   SET status = 'sent', sent_at = :now, subject = :subject,
                       preview = :preview, provider_message_id = :provider_id,
                       error = NULL
                 WHERE id = :id
                """
            ),
            {
                "id": notification_id,
                "now": now,
                "subject": subject[:200],
                "preview": preview[:200],
                "provider_id": provider_message_id[:120] if provider_message_id else None,
            },
        )

    async def mark_failed(self, notification_id: uuid.UUID, *, error: str, now: datetime) -> None:
        # `attempts` increments here rather than on claim-retry, because a row
        # is only claimed once — the count that matters is how many times
        # delivery was attempted against it.
        await self._session.execute(
            text(
                """
                UPDATE notifications
                   SET status = 'failed', failed_at = :now, error = :error,
                       attempts = attempts + 1
                 WHERE id = :id
                """
            ),
            {"id": notification_id, "now": now, "error": error[:2000]},
        )

    async def mark_suppressed(
        self, notification_id: uuid.UUID, *, reason: str, now: datetime
    ) -> None:
        await self._session.execute(
            text(
                """
                UPDATE notifications
                   SET status = 'suppressed', failed_at = :now, error = :reason
                 WHERE id = :id
                """
            ),
            {"id": notification_id, "now": now, "reason": reason[:2000]},
        )


def _json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, default=str)
