"""The notification worker.

One task, subscribed to the auth events that gate getting into the product.
It is on the **critical** queue: a verification mail behind a batch of image
processing is a signup that appears broken, and the person has already closed
the tab by the time it arrives.

Retries are for transport failures only. The use case records permanent
failures — an unknown template, a context missing a variable — and returns
rather than raising, so those are not retried five times to fail identically.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.logging import get_logger
from app.infrastructure.queue.async_bridge import run_async
from app.infrastructure.queue.celery_app import QueueName, celery_app
from app.modules.notification.application.use_cases import SendNotificationUseCase
from app.modules.notification.domain import templates

logger = get_logger(__name__)

#: event_type -> the template it produces.
#:
#: Kept here rather than in `SUBSCRIPTIONS` because it is this module's
#: business which message an event turns into. The dispatcher's job ends at
#: "notification cares about this event".
_TEMPLATE_FOR: dict[str, str] = {
    "auth.email.verification_requested": templates.EMAIL_VERIFICATION,
    "auth.password.reset_requested": templates.PASSWORD_RESET,
}


async def _send(event_type: str, event_id: str, payload: dict[str, Any]) -> str:
    from app.container import get_container

    template = _TEMPLATE_FOR.get(event_type)
    if template is None:  # pragma: no cover — unreachable while SUBSCRIPTIONS agrees
        logger.error("notification_unmapped_event", event_type=event_type)
        return "unmapped"

    recipient = str(payload.get("email") or "").strip()
    if not recipient:
        logger.error("notification_no_recipient", event_type=event_type, event_id=event_id)
        return "no-recipient"

    container = await get_container()
    settings = container.settings.email

    async with container.database.write_session() as session:
        from app.modules.notification.infrastructure.repositories import SqlNotificationLog

        use_case = SendNotificationUseCase(
            log=SqlNotificationLog(session),
            sender=container.email_sender,
            clock=container.clock,
            web_base_url=settings.web_base_url,
            enabled=settings.enabled,
        )
        result = await use_case.execute(
            template=template,
            recipient=recipient,
            context=dict(payload),
            # The **event** id, not the aggregate id. Keying on the user would
            # make a second, legitimate password reset a duplicate of the
            # first — a person who asks twice must get two mails. Keying on the
            # event makes exactly the redeliveries idempotent, which is what
            # at-least-once delivery from the relay actually produces.
            dedupe_key=f"{template}:{event_id}",
            user_id=_uuid_or_none(payload.get("user_id")),
        )
        # Commit is the session context manager's job; the row and the send are
        # not in one transaction and cannot be — see the ordering note in the
        # use case.
        return result.status


def _uuid_or_none(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


@celery_app.task(
    name="app.modules.notification.tasks.send_notification",
    queue=QueueName.CRITICAL,
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
    ignore_result=True,
)
def send_notification(
    self: Any,
    *,
    event_id: str,
    aggregate_id: str,
    event_version: int,
    payload: dict[str, Any],
    event_type: str | None = None,
    # Same forward-compatibility rule every consumer follows: a field added to
    # the dispatch payload must not break messages already in the queue.
    **_: Any,
) -> str:
    """Turn one auth event into one email.

    `event_type` is optional in the signature because the dispatcher did not
    always pass it; a redelivery of an event queued by an older build would
    otherwise fail with a `TypeError` on unpickling rather than being handled.
    """
    if not event_type:  # pragma: no cover — only for in-flight legacy messages
        logger.error("notification_missing_event_type", event_id=event_id)
        return "unmapped"
    return str(run_async(_send(event_type, event_id, payload)))
