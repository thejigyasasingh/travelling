"""Background AI work.

Everything expensive runs here rather than in a request. A guest posting a
review waits for the review to be stored, not for a model to read it; a host
uploading twelve photographs waits for twelve uploads, not twelve vision calls.

All of these are driven by the outbox and are therefore **at-least-once**. Each
is idempotent on a content hash, so a redelivery is a no-op rather than a
duplicate charge — see :mod:`app.modules.ai.application.use_cases.analysis`.

None of them retry on a model failure. A review whose analysis failed is a
review with no sentiment badge, which is invisible; retrying a provider outage
across thousands of queued reviews turns a degraded feature into a bill.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text

from app.core.logging import get_logger
from app.infrastructure.queue.async_bridge import run_async
from app.infrastructure.queue.celery_app import QueueName, celery_app
from app.modules.ai.application.use_cases.analysis import (
    AnalyseReview,
    TagImage,
    annotation_to_row,
    content_hash,
    insight_to_row,
)
from app.modules.ai.domain import errors
from app.modules.ai.infrastructure.unit_of_work import AIUow

logger = get_logger(__name__)

#: Chat transcripts are guest-authored free text and are retained only as long
#: as a conversation is plausibly still going.
MESSAGE_RETENTION_DAYS = 30


async def _uow() -> tuple[Any, AIUow]:
    from app.container import get_container

    container = await get_container()
    session = container.database.write_session_factory()
    return container, AIUow(session)


# ══════════════════════════════════════════════════════════════════════════
# Review sentiment
# ══════════════════════════════════════════════════════════════════════════


async def _analyse_review(review_id: uuid.UUID) -> str:
    container, uow = await _uow()
    if not container.language_model.available:
        return "skipped_model_unavailable"

    try:
        row = (
            await uow.session.execute(
                text(
                    "SELECT property_id, title, body, rating, moderation "
                    "  FROM reviews WHERE id = :id"
                ),
                {"id": review_id},
            )
        ).first()
        if row is None:
            # Deleted between the event and this task. Normal, not an error.
            return "gone"
        property_id, title, body, rating, moderation = row

        if moderation == "removed":
            # Analysing a review staff took down would put its summary on the
            # property page through a different door.
            return "removed"

        digest = content_hash(str(title or ""), str(body), str(rating))
        insight = await AnalyseReview(container.language_model).execute(
            title=title, body=body, rating=int(rating)
        )

        changed = await uow.store.save_insight(
            review_id=review_id,
            property_id=property_id,
            row=insight_to_row(insight, review_id=review_id),
            model=container.settings.ai.fast_model,
            content_hash=digest,
        )
        if changed:
            await uow.store.rebuild_sentiment(property_id)
        await uow.commit()

        if insight.needs_attention:
            # Logged at warning so it is visible without the queue being read.
            # The queue is the durable record; this is the page.
            logger.warning(
                "review_needs_attention",
                review_id=str(review_id),
                property_id=str(property_id),
                reason=insight.attention_reason,
            )
        return "analysed" if changed else "unchanged"
    except errors.ModelUnavailableError:
        return "skipped_model_unavailable"
    finally:
        await uow.session.close()


@celery_app.task(
    name="app.modules.ai.tasks.analyse_review",
    queue=QueueName.DEFAULT,
    autoretry_for=(),
    ignore_result=True,
)
def analyse_review(
    *, aggregate_id: str, payload: dict[str, Any], **_: Any
) -> str:  # pragma: no cover — exercised end to end
    """Subscriber for ``review.published`` and ``review.edited``."""
    del payload
    return run_async(_analyse_review(uuid.UUID(aggregate_id)))


# ══════════════════════════════════════════════════════════════════════════
# Image tagging
# ══════════════════════════════════════════════════════════════════════════


async def _tag_image(image_id: uuid.UUID) -> str:
    container, uow = await _uow()
    if not container.language_model.available:
        return "skipped_model_unavailable"

    try:
        row = (
            await uow.session.execute(
                text(
                    "SELECT i.property_id, i.storage_key   FROM property_images i WHERE i.id = :id"
                ),
                {"id": image_id},
            )
        ).first()
        if row is None:
            return "gone"
        property_id, storage_key = row

        image_bytes, media_type = await container.storage.fetch(storage_key)
        # Hashing the bytes, not the key: a host who replaces a photograph at
        # the same key gets it re-tagged, and one whose key changed but whose
        # image did not does not pay twice.
        digest = content_hash(str(len(image_bytes)), content_hash(image_bytes.hex()[:4096]))

        catalogue = {
            str(r[0]) for r in (await uow.session.execute(text("SELECT code FROM amenities"))).all()
        }
        annotation = await TagImage(container.language_model).execute(
            image_bytes=image_bytes,
            media_type=media_type,
            known_amenities=frozenset(catalogue),
        )

        await uow.store.save_annotation(
            image_id=image_id,
            property_id=property_id,
            row=annotation_to_row(annotation),
            model=container.settings.ai.fast_model,
            content_hash=digest,
        )
        await uow.commit()

        if annotation.flagged:
            logger.warning(
                "image_flagged_by_model",
                image_id=str(image_id),
                property_id=str(property_id),
                reason=annotation.flag_reason,
            )
        return "tagged"
    except errors.ModelUnavailableError:
        return "skipped_model_unavailable"
    except FileNotFoundError:
        return "gone"
    finally:
        await uow.session.close()


@celery_app.task(
    name="app.modules.ai.tasks.tag_image",
    queue=QueueName.DEFAULT,
    autoretry_for=(),
    ignore_result=True,
)
def tag_image(*, aggregate_id: str, payload: dict[str, Any], **_: Any) -> str:  # pragma: no cover
    """Subscriber for ``property.image_added``."""
    image_id = payload.get("image_id")
    if not image_id:
        logger.warning("tag_image_missing_image_id", aggregate_id=aggregate_id)
        return "no_image_id"
    return run_async(_tag_image(uuid.UUID(str(image_id))))


# ══════════════════════════════════════════════════════════════════════════
# Cache invalidation and retention
# ══════════════════════════════════════════════════════════════════════════


async def _invalidate_itineraries(property_id: uuid.UUID) -> int:
    _, uow = await _uow()
    try:
        count = await uow.store.invalidate_itineraries_referencing(property_id)
        await uow.commit()
        return count
    finally:
        await uow.session.close()


@celery_app.task(
    name="app.modules.ai.tasks.invalidate_itineraries",
    queue=QueueName.DEFAULT,
    autoretry_for=(),
    ignore_result=True,
)
def invalidate_itineraries(*, aggregate_id: str, **_: Any) -> int:  # pragma: no cover
    """Subscriber for ``property.unpublished``.

    A cached plan that recommends basing yourself at a hotel which has since
    been taken off sale is a plan that ends in a 404. Cheap to expire, and the
    next request regenerates.
    """
    return run_async(_invalidate_itineraries(uuid.UUID(aggregate_id)))


async def _purge_messages() -> int:
    _, uow = await _uow()
    try:
        deleted = await uow.store.purge_messages_older_than(MESSAGE_RETENTION_DAYS)
        await uow.commit()
        if deleted:
            logger.info("assistant_messages_purged", deleted=deleted)
        return deleted
    finally:
        await uow.session.close()


@celery_app.task(
    name="app.modules.ai.tasks.purge_assistant_messages",
    queue=QueueName.DEFAULT,
    ignore_result=True,
)
def purge_assistant_messages() -> int:  # pragma: no cover
    """Retention. Chat transcripts contain whatever guests typed, and some
    fraction of people type a phone number into any box."""
    return run_async(_purge_messages())
