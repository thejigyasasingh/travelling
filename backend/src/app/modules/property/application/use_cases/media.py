"""Listing photos.

Uploads are **direct to S3**, in two steps:

1. ``POST /images/upload-url`` — the server generates the key and returns a
   presigned POST policy. The key encodes the property, so a client cannot
   write into another vendor's prefix; the policy pins the content type and a
   hard size ceiling that S3 itself enforces.
2. ``POST /images`` — the client tells us the upload finished, and the server
   **verifies with a HEAD** before creating the row.

Step 2's verification is the part that is easy to skip and wrong to skip. A
client that says "I uploaded it" and did not would otherwise leave a listing
with a broken image that passes the publish check and renders as a grey box in
search. The HEAD also gives us the *real* size and content type rather than the
ones the client claimed.

The API never touches image bytes — see ``infrastructure/storage/s3.py`` for
why proxying a 20 MB photo through a worker is a self-inflicted outage.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Final

from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.modules.property.application.dto import (
    ConfirmImageInput,
    ImageView,
    RequestImageUploadInput,
)
from app.modules.property.application.ports import (
    ImageUrlBuilder,
    MediaStorage,
    PropertyRepository,
)
from app.modules.property.domain import errors
from app.modules.property.domain.entities import MAX_IMAGES, PropertyImage
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)

ALLOWED_TYPES: Final = frozenset({"image/jpeg", "image/png", "image/webp", "image/avif"})
MAX_IMAGE_BYTES: Final = 15 * 1024 * 1024
#: Below this a "photo" is a thumbnail, an icon or a placeholder, and it makes
#: the listing look abandoned. Cheap to reject at confirm time.
MIN_IMAGE_BYTES: Final = 10 * 1024
MAX_BATCH: Final = 10


@dataclass(slots=True)
class RequestImageUploadUseCase:
    properties: PropertyRepository
    storage: MediaStorage

    async def execute(self, data: RequestImageUploadInput, actor: Actor) -> list[dict[str, Any]]:
        prop = await self.properties.get_for_vendor(
            data.property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", data.property_id)
        prop.assert_owned_by(actor.vendor_id)
        prop.assert_editable()

        if len(data.filenames) != len(data.content_types):
            raise ValidationError("filenames and content_types must be the same length")
        if not data.filenames:
            raise ValidationError("At least one file is required")
        if len(data.filenames) > MAX_BATCH:
            raise ValidationError(f"At most {MAX_BATCH} files may be requested at once")
        if len(prop.images) + len(data.filenames) > MAX_IMAGES:
            raise errors.ImageLimitError(MAX_IMAGES)

        tickets: list[dict[str, Any]] = []
        for filename, content_type in zip(data.filenames, data.content_types, strict=True):
            if content_type not in ALLOWED_TYPES:
                raise ValidationError(
                    f"Unsupported image type {content_type!r}",
                    details={"allowed": sorted(ALLOWED_TYPES)},
                )
            # Server-generated. A client-supplied key is a path traversal and
            # an overwrite of another vendor's object.
            key = self.storage.build_key(
                scope=f"properties/{prop.id}", owner_id=prop.vendor_id, filename=filename
            )
            policy = await self.storage.presign_upload(
                key, content_type=content_type, max_bytes=MAX_IMAGE_BYTES
            )
            tickets.append(policy)

        logger.info("image_upload_urls_issued", property_id=str(prop.id), count=len(tickets))
        return tickets


@dataclass(slots=True)
class ConfirmImagesUseCase:
    properties: PropertyRepository
    storage: MediaStorage
    urls: ImageUrlBuilder

    async def execute(self, data: ConfirmImageInput, actor: Actor) -> list[ImageView]:
        prop = await self.properties.get_for_vendor(
            data.property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", data.property_id)
        prop.assert_owned_by(actor.vendor_id)
        prop.assert_editable()

        expected_prefix = f"properties/{prop.id}/"
        images: list[PropertyImage] = []

        for index, key in enumerate(data.storage_keys):
            # The key came back from the client, so it is untrusted even though
            # we generated it. Without this check a vendor could claim an
            # object belonging to a different property.
            if not key.startswith(expected_prefix):
                raise ValidationError(
                    "Storage key does not belong to this property",
                    details={"key": key},
                )

            meta = await self.storage.head(key)
            if meta is None:
                # The client said it uploaded and it did not. Failing here
                # keeps a broken image out of the listing.
                raise ValidationError(
                    "That upload was not found. Please upload the file before confirming.",
                    details={"key": key},
                )
            if meta["size"] < MIN_IMAGE_BYTES:
                raise ValidationError(
                    "That image is too small to display well.",
                    details={"key": key, "min_bytes": MIN_IMAGE_BYTES},
                )
            if meta.get("content_type") not in ALLOWED_TYPES:
                # The presigned policy pinned the declared type, but the actual
                # object is what matters — a mismatch means something odd.
                raise ValidationError(
                    "That file is not a supported image.",
                    details={"key": key, "content_type": meta.get("content_type")},
                )

            alt_texts: list[str | None] = list(data.alt_texts or [])
            alt = alt_texts[index] if index < len(alt_texts) else None
            images.append(PropertyImage(storage_key=key, alt_text=alt))

        # Assigns positions, promotes the first image to cover if none is set,
        # and records ImagesUploaded for the thumbnail/moderation consumers.
        prop.add_images(images)

        logger.info("images_confirmed", property_id=str(prop.id), count=len(images))
        return [
            ImageView(
                id=img.id,
                url=self.urls.public_url(img.storage_key),
                position=img.position,
                is_cover=img.is_cover,
                alt_text=img.alt_text,
            )
            for img in images
        ]


@dataclass(slots=True)
class DeleteImageUseCase:
    properties: PropertyRepository

    async def execute(self, args: tuple[uuid.UUID, uuid.UUID], actor: Actor) -> None:
        """Remove a photo.

        The S3 object is **not** deleted here. `ImageRemoved` goes to the
        outbox and a consumer deletes it — an inline S3 call inside the
        transaction would leave the object gone if the transaction then rolled
        back, and would put a network round trip in the request path.
        """
        property_id, image_id = args
        prop = await self.properties.get_for_vendor(
            property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", property_id)
        prop.assert_owned_by(actor.vendor_id)

        prop.remove_image(image_id)
        logger.info("image_removed", property_id=str(prop.id), image_id=str(image_id))


@dataclass(slots=True)
class ReorderImagesUseCase:
    properties: PropertyRepository
    urls: ImageUrlBuilder

    async def execute(
        self, args: tuple[uuid.UUID, list[uuid.UUID], uuid.UUID | None], actor: Actor
    ) -> list[ImageView]:
        property_id, ordered_ids, cover_id = args
        prop = await self.properties.get_for_vendor(
            property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", property_id)
        prop.assert_owned_by(actor.vendor_id)

        if ordered_ids:
            prop.reorder_images(ordered_ids)
        if cover_id is not None:
            prop.set_cover_image(cover_id)

        return [
            ImageView(
                id=img.id,
                url=self.urls.public_url(img.storage_key),
                position=img.position,
                is_cover=img.is_cover,
                alt_text=img.alt_text,
                caption=img.caption,
            )
            for img in sorted(prop.images, key=lambda i: i.position)
        ]
