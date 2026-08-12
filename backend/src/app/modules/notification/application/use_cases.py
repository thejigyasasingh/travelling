"""Send one notification, exactly once, and record what happened.

The whole module in one class, because the ordering is the design and it reads
better in one place than spread across four:

1. **Claim first.** A `queued` row goes in before anything is rendered or sent,
   keyed by `dedupe_key`. If the insert loses the unique-index race, another
   worker already has this message and we stop — the second delivery never
   happens, decided by Postgres rather than by a read-then-write check that has
   a window in it.
2. **Render second.** A template that does not exist, or a context missing a
   variable, is a permanent failure. It is recorded as one and *not* retried:
   the fifth attempt renders exactly as badly as the first.
3. **Send third, and only then mark sent.** Marking before sending would
   suppress the retry of a message that never left.

The failure mode this ordering accepts, deliberately: if the process dies
between a successful SMTP handshake and the `mark_sent` commit, the row stays
`queued` and the dedupe key is taken — so the message is delivered but recorded
as pending, and the retry is suppressed. One delivered-but-unrecorded message
is strictly better than the alternative ordering's one recorded-but-undelivered
password reset, which is a person locked out of their account.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from prometheus_client import Counter

from app.core.clock import Clock
from app.core.logging import get_logger
from app.modules.notification.application.ports import EmailSender, NotificationLog
from app.modules.notification.domain import templates

logger = get_logger(__name__)

#: Every send attempt, by outcome.
#:
#: A metric rather than only a log line, because the failure this module exists
#: to end was *silent*: verification mail was dropped for the whole early life
#: of the platform and nothing about it was visible on any dashboard. A counter
#: with a `sent`/`failed`/`suppressed`/`duplicate` label makes "signups have
#: been broken since Tuesday" a graph rather than a support ticket.
#:
#: Labelled by template too: a rise in failures for one template — a bad link
#: host, a provider rejecting one From address — looks completely different
#: from the mailer being down, and the alert wants to tell them apart.
notifications_total = Counter(
    "notifications_total",
    "Notification send attempts by template and outcome",
    labelnames=("template", "outcome"),
)

EMAIL = "email"

#: Context keys never written to the notification log.
#:
#: The log stores the render context so a failed send can be replayed exactly —
#: which is useful, and would also mean every password-reset token sitting in a
#: queryable table for as long as the row lives. A replay mints a fresh token
#: anyway, so the stored copy buys nothing and costs a credential store.
_UNLOGGABLE = frozenset({"token", "otp", "code", "password", "secret"})


def _loggable(context: dict[str, Any]) -> dict[str, Any]:
    return {k: ("[REDACTED]" if k in _UNLOGGABLE else v) for k, v in context.items()}


@dataclass(frozen=True)
class SendResult:
    status: str
    notification_id: uuid.UUID | None = None


class SendNotificationUseCase:
    def __init__(
        self,
        *,
        log: NotificationLog,
        sender: EmailSender,
        clock: Clock,
        web_base_url: str,
        enabled: bool,
    ) -> None:
        self._log = log
        self._sender = sender
        self._clock = clock
        self._web_base_url = web_base_url
        self._enabled = enabled

    async def execute(
        self,
        *,
        template: str,
        recipient: str,
        context: dict[str, Any],
        dedupe_key: str,
        user_id: uuid.UUID | None = None,
    ) -> SendResult:
        now = self._clock.now()

        notification_id = await self._log.claim(
            channel=EMAIL,
            template=template,
            recipient=recipient,
            user_id=user_id,
            context=_loggable(context),
            dedupe_key=dedupe_key,
            now=now,
        )
        if notification_id is None:
            # Not an error, and the common case under redelivery. The relay is
            # at-least-once by design; this is where that becomes effectively
            # once.
            logger.info("notification_duplicate", template=template, dedupe_key=dedupe_key)
            notifications_total.labels(template=template, outcome="duplicate").inc()
            return SendResult(status="duplicate")

        try:
            message = templates.render(template, context, web_base_url=self._web_base_url)
        except (templates.UnknownTemplateError, KeyError, ValueError) as exc:
            # Permanent. Recorded and not raised, so Celery does not retry a
            # message that cannot be built.
            await self._log.mark_failed(
                notification_id, error=f"render: {exc!r}", now=self._clock.now()
            )
            logger.error("notification_unrenderable", template=template, error=str(exc))
            notifications_total.labels(template=template, outcome="failed").inc()
            return SendResult(status="failed", notification_id=notification_id)

        if not self._enabled:
            # Recorded as suppressed rather than dropped. The difference is
            # whether an operator can tell, three days later, that signups have
            # been failing because nothing was ever configured.
            await self._log.mark_suppressed(
                notification_id, reason="email disabled", now=self._clock.now()
            )
            logger.warning("notification_suppressed", template=template, reason="email disabled")
            notifications_total.labels(template=template, outcome="suppressed").inc()
            return SendResult(status="suppressed", notification_id=notification_id)

        try:
            provider_id = await self._sender.send(
                to=recipient,
                subject=message.subject,
                text=message.text,
                html=message.html,
            )
        except Exception as exc:
            # Transient — a refused connection, a greylisting, a timeout. The
            # row records the attempt and the exception propagates so Celery's
            # retry policy decides what happens next.
            await self._log.mark_failed(
                notification_id, error=repr(exc)[:2000], now=self._clock.now()
            )
            logger.warning("notification_send_failed", template=template, error=str(exc))
            notifications_total.labels(template=template, outcome="failed").inc()
            raise

        await self._log.mark_sent(
            notification_id,
            subject=message.subject,
            preview=message.preview,
            provider_message_id=provider_id,
            now=self._clock.now(),
        )
        logger.info("notification_sent", template=template, notification_id=str(notification_id))
        notifications_total.labels(template=template, outcome="sent").inc()
        return SendResult(status="sent", notification_id=notification_id)
