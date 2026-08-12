"""The notification log.

Every message the platform sends a person, recorded. Not for nostalgia — three
concrete needs:

* **Support has to answer "did they get the email?"** without asking the
  provider, on the phone, while the guest waits.
* **Delivery failures need somewhere to be seen.** A bounced confirmation is a
  guest who will arrive at a property with nothing to show, and if it is only
  in a provider dashboard nobody looks at it.
* **Duplicate suppression needs a record.** A retried Celery task must not send
  the same confirmation twice, and `dedupe_key` is what makes that decidable.

The **body is not stored** — only the template, the variables it needed, and a
short preview. A confirmation body contains the guest's address and their
booking reference; a table of rendered bodies is a data-protection liability
that grows forever for no operational benefit.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base
from app.infrastructure.database.mixins import UUIDPrimaryKeyMixin


class NotificationModel(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "notifications"

    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    template: Mapped[str] = mapped_column(String(60), nullable=False)

    user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    #: Stored so support can search by what the guest typed, and because a
    #: recipient may have no account at all.
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)

    subject: Mapped[str | None] = mapped_column(String(200))
    #: A short preview only — never the rendered body. See the module docstring.
    preview: Mapped[str | None] = mapped_column(String(200))
    #: The variables the template was rendered with, so a failed send can be
    #: replayed exactly. PII-bearing keys are redacted before they land here.
    context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default=text("'queued'"))
    provider_message_id: Mapped[str | None] = mapped_column(String(120))
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    #: What makes a retried task idempotent. Usually
    #: `{template}:{aggregate_id}`, so the same confirmation cannot be sent
    #: twice however many times the job runs.
    dedupe_key: Mapped[str | None] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_notifications_dedupe"),
        CheckConstraint("channel IN ('email','sms','push','whatsapp')", name="channel_valid"),
        CheckConstraint("status IN ('queued','sent','failed','suppressed')", name="status_valid"),
        # "Did they get it?" — support's first question, answered by recipient.
        Index("ix_notifications_recipient", "recipient", text("created_at DESC")),
        # The failure queue. Partial, because failures are a small fraction and
        # this index is scanned by an alert, not by a person.
        Index(
            "ix_notifications_failed",
            "created_at",
            postgresql_where=text("status = 'failed'"),
        ),
        Index("ix_notifications_template", "template", text("created_at DESC")),
    )
