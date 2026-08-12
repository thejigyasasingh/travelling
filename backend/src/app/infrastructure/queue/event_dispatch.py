"""The other end of the outbox relay.

``relay_batch`` sends every outbox row to ``app.events.dispatch``; this is the
task that receives it and fans it out to whichever module subscribed.

Why a routing table rather than each module listening directly: the relay must
know nothing about consumers, and consumers must not import each other. A
dict of ``event_type -> [task names]`` keeps the coupling to one line per
subscription, in one file, that anyone can read to answer "what happens when a
booking is cancelled?".

**Delivery is at-least-once.** The relay marks a row processed only after
``send_task`` returns, so a crash in between redelivers it. Every handler is
therefore idempotent on its own — the dispatcher does not and cannot dedupe.
"""

from __future__ import annotations

from typing import Any, Final

from app.core.logging import get_logger
from app.infrastructure.queue.celery_app import QueueName, celery_app

logger = get_logger(__name__)

#: event_type -> Celery task names. An event with no entry is dropped, which is
#: the normal case: most events exist for the audit trail and for consumers
#: that do not exist yet.
SUBSCRIPTIONS: Final[dict[str, tuple[str, ...]]] = {
    # ── the two events that gate getting into the product ────────────────
    #
    # These were emitted, written to the outbox, and dropped here for the
    # entire history of the system, because "an event with no entry is
    # dropped" is the normal case and nothing distinguished these two from an
    # event kept only for the audit trail. The effect was that no user could
    # ever verify an address or reset a password: registration returned
    # `202 unverified` and the mail was discarded three hops later, with no
    # error anywhere.
    #
    # If a row is ever removed from this table, check first whether anything
    # downstream is the only consumer of it.
    "auth.email.verification_requested": ("app.modules.notification.tasks.send_notification",),
    "auth.password.reset_requested": ("app.modules.notification.tasks.send_notification",),
    # Booking decided *what* to refund; payment knows *how*. This one line is
    # the entire coupling between the two modules in that direction.
    "booking.refund.requested": ("app.modules.payment.tasks.execute_refund",),
    # Sentiment analysis runs off the request path. A guest pressing "post
    # review" waits for the review to be stored, not for a model to read it.
    "review.published": ("app.modules.ai.tasks.analyse_review",),
    # An edit replaces the words the analysis described. Same task; it is
    # idempotent on a hash of the text, so an unchanged redelivery costs
    # nothing and a real edit is re-analysed.
    "review.edited": ("app.modules.ai.tasks.analyse_review",),
    # A cached itinerary recommending a listing that has since been taken off
    # sale is a plan that ends in a 404.
    "property.unpublished": ("app.modules.ai.tasks.invalidate_itineraries",),
}


@celery_app.task(
    name="app.events.dispatch",
    queue=QueueName.CRITICAL,
    autoretry_for=(),  # the relay redelivers; a retry here would double it
    ignore_result=True,
)
def dispatch_event(
    *,
    event_id: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    event_version: int,
    payload: dict[str, Any],
) -> int:  # pragma: no cover — covered indirectly; the table is asserted in test_task_registry
    """Fan one event out to its subscribers. Returns how many were queued."""
    handlers = SUBSCRIPTIONS.get(event_type, ())
    if not handlers:
        logger.debug("event_no_subscribers", event_type=event_type, event_id=event_id)
        return 0

    for task_name in handlers:
        celery_app.send_task(
            task_name,
            kwargs={
                "event_id": event_id,
                # Passed because a consumer may legitimately subscribe to more
                # than one event and behave differently for each — the
                # notification worker turns two different auth events into two
                # different messages through one task. Without this it would
                # need a task per event type, and the dispatch table would
                # encode which *message* to send rather than which module
                # cares.
                #
                # Every consumer therefore accepts `**_`, so adding a field
                # here is not a breaking change to tasks already queued.
                "event_type": event_type,
                "aggregate_id": aggregate_id,
                "event_version": event_version,
                "payload": payload,
            },
            queue=QueueName.CRITICAL,
        )

    logger.info(
        "event_dispatched",
        event_type=event_type,
        event_id=event_id,
        aggregate_id=aggregate_id,
        handlers=len(handlers),
    )
    return len(handlers)
