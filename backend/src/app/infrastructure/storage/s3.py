"""Object storage — S3 in the cloud, MinIO locally.

**Uploads never touch the API.** The client asks for a presigned POST policy
and uploads directly to S3. Proxying a 20 MB property photo through FastAPI
occupies a worker for the length of a hotel manager's 4G upload; a hundred
concurrent uploads is a stalled API with a healthy CPU graph and no obvious
cause.

The presigned policy enforces what the API otherwise could not, because it
never sees the bytes:

* ``content-length-range`` — a hard size cap, checked by S3.
* ``Content-Type`` — pinned to the declared type.
* a 15-minute expiry, and a server-generated key.

**Keys are server-generated, always.** A client-supplied key is a path
traversal (``../../other-vendor/x.jpg``) and an overwrite of someone else's
object. The key encodes owner and purpose so that access control is derivable
from the path itself.

The boto3 client is synchronous and is called via ``asyncio.to_thread`` —
presigning is pure local crypto (sub-millisecond, no network), so a thread hop
is cheaper than pulling in an async AWS SDK for it.
"""

from __future__ import annotations

import asyncio
import mimetypes
import uuid
from collections.abc import Mapping
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from uuid_utils.compat import uuid7

from app.core.config import StorageSettings
from app.core.errors import DependencyUnavailableError, ValidationError
from app.core.logging import get_logger

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client
else:
    S3Client = Any

logger = get_logger(__name__)

ALLOWED_IMAGE_TYPES: Final = frozenset({"image/jpeg", "image/png", "image/webp", "image/avif"})
ALLOWED_DOC_TYPES: Final = frozenset({"application/pdf"})
MAX_IMAGE_BYTES: Final = 15 * 1024 * 1024
MAX_DOC_BYTES: Final = 10 * 1024 * 1024


class S3Storage:
    """Implements :class:`app.shared.application.ports.StoragePort`."""

    def __init__(self, settings: StorageSettings) -> None:
        self._settings = settings
        self._bucket = settings.bucket
        self._client: S3Client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,  # None => real AWS
            region_name=settings.region,
            aws_access_key_id=(
                settings.access_key.get_secret_value() if settings.access_key else None
            ),
            aws_secret_access_key=(
                settings.secret_key.get_secret_value() if settings.secret_key else None
            ),
            config=BotoConfig(
                signature_version="s3v4",  # required for presigned POST with conditions
                s3={"addressing_style": "path"},  # MinIO cannot do virtual-host style
                retries={"max_attempts": 2, "mode": "standard"},
                connect_timeout=3,
                read_timeout=10,
            ),
        )

    # ── key construction ──────────────────────────────────────────────────

    @staticmethod
    def build_key(*, scope: str, owner_id: uuid.UUID, filename: str) -> str:
        """``{scope}/{owner}/{uuid7}{ext}``.

        UUIDv7 keeps keys roughly time-ordered, which makes lifecycle rules and
        prefix listings behave predictably. Only the extension survives from the
        client's filename — the rest is discarded rather than sanitised, because
        sanitising attacker-controlled paths is a game you eventually lose.
        """
        ext = ""
        if "." in filename:
            candidate = "." + filename.rsplit(".", 1)[-1].lower()
            if len(candidate) <= 6 and candidate[1:].isalnum():
                ext = candidate
        return f"{scope}/{owner_id}/{uuid7()}{ext}"

    # ── presigning ────────────────────────────────────────────────────────

    async def presign_upload(
        self,
        key: str,
        *,
        content_type: str,
        max_bytes: int = MAX_IMAGE_BYTES,
        allowed_types: frozenset[str] = ALLOWED_IMAGE_TYPES,
    ) -> dict[str, Any]:
        if content_type not in allowed_types:
            raise ValidationError(
                f"Unsupported content type {content_type!r}",
                details={"allowed": sorted(allowed_types)},
            )

        expires = self._settings.presign_ttl_seconds

        def _sign() -> dict[str, Any]:
            return self._client.generate_presigned_post(
                Bucket=self._bucket,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    # S3 rejects the upload itself if this is exceeded. The API
                    # cannot enforce a size limit on bytes it never receives.
                    ["content-length-range", 1, max_bytes],
                ],
                ExpiresIn=expires,
            )

        try:
            policy = await asyncio.to_thread(_sign)
        except (ClientError, BotoCoreError) as exc:
            logger.error("presign_upload_failed", key=key, error=str(exc))
            raise DependencyUnavailableError("object-storage") from exc

        return {
            "url": policy["url"],
            "fields": policy["fields"],
            "key": key,
            "expires_in": expires,
            "max_bytes": max_bytes,
        }

    async def presign_download(self, key: str, *, expires_in: timedelta | None = None) -> str:
        """Short-lived read URL for private objects (ID documents, invoices).

        Public listing photos are served from CloudFront instead — presigning
        those would defeat CDN caching entirely, since every user would get a
        distinct signed URL.
        """
        default_ttl = timedelta(seconds=self._settings.presign_ttl_seconds)
        ttl = int((expires_in or default_ttl).total_seconds())

        def _sign() -> str:
            return self._client.generate_presigned_url(
                "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=ttl
            )

        try:
            return await asyncio.to_thread(_sign)
        except (ClientError, BotoCoreError) as exc:
            logger.error("presign_download_failed", key=key, error=str(exc))
            raise DependencyUnavailableError("object-storage") from exc

    # ── object operations ─────────────────────────────────────────────────

    async def head(self, key: str) -> dict[str, Any] | None:
        """Confirm a presigned upload actually happened, and learn its real
        size and type. The client's claim about what it uploaded is not
        evidence."""

        def _head() -> Mapping[str, Any]:
            return self._client.head_object(Bucket=self._bucket, Key=key)

        try:
            meta = await asyncio.to_thread(_head)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                return None
            raise DependencyUnavailableError("object-storage") from exc
        return {
            "size": meta["ContentLength"],
            "content_type": meta.get("ContentType"),
            "etag": meta.get("ETag", "").strip('"'),
        }

    #: Vision models are sent whole images, so a malicious or careless upload
    #: is an inbound cost as well as a storage one. Nothing above this size is
    #: worth analysing and everything above it is worth refusing.
    MAX_FETCH_BYTES = 8 * 1024 * 1024

    async def fetch(self, key: str) -> tuple[bytes, str]:
        """Download an object into memory, for server-side analysis.

        Bounded, unlike a presigned download: the caller here is our own
        worker feeding bytes to a model that charges by the token, and an
        unbounded read is an unbounded bill as well as an unbounded heap.

        Raises ``FileNotFoundError`` for a missing key, which callers treat as
        "deleted since the event" rather than as a failure.
        """

        def _get() -> tuple[bytes, str]:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            length = int(response.get("ContentLength", 0))
            if length > self.MAX_FETCH_BYTES:
                msg = f"{key} is {length} bytes, over the {self.MAX_FETCH_BYTES} limit"
                raise ValueError(msg)
            # Read one byte past the limit so a lying or absent ContentLength
            # cannot get around the check above.
            body = response["Body"].read(self.MAX_FETCH_BYTES + 1)
            if len(body) > self.MAX_FETCH_BYTES:
                msg = f"{key} exceeds the {self.MAX_FETCH_BYTES} byte limit"
                raise ValueError(msg)
            return body, str(response.get("ContentType") or "application/octet-stream")

        try:
            return await asyncio.to_thread(_get)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                raise FileNotFoundError(key) from exc
            logger.error("s3_fetch_failed", key=key, error=str(exc))
            raise DependencyUnavailableError("object-storage") from exc
        except BotoCoreError as exc:  # pragma: no cover
            raise DependencyUnavailableError("object-storage") from exc

    async def delete(self, key: str) -> None:
        def _delete() -> None:
            self._client.delete_object(Bucket=self._bucket, Key=key)

        try:
            await asyncio.to_thread(_delete)
        except (ClientError, BotoCoreError) as exc:  # pragma: no cover
            logger.error("s3_delete_failed", key=key, error=str(exc))

    async def ensure_bucket(self) -> None:
        """Local convenience only — creates the MinIO bucket on first boot.

        Guarded by ``endpoint_url``: in AWS the bucket is Terraform's job, and
        an application that can create buckets has more IAM permission than it
        should.
        """
        if not self._settings.endpoint_url:
            return

        def _ensure() -> None:
            try:
                self._client.head_bucket(Bucket=self._bucket)
            except ClientError:
                self._client.create_bucket(Bucket=self._bucket)

        try:
            await asyncio.to_thread(_ensure)
            logger.info("bucket_ready", bucket=self._bucket)
        except (ClientError, BotoCoreError) as exc:  # pragma: no cover
            logger.warning("bucket_setup_failed", error=str(exc))

    async def ping(self) -> bool:
        def _ping() -> None:
            self._client.head_bucket(Bucket=self._bucket)

        await asyncio.to_thread(_ping)
        return True


def guess_content_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"
