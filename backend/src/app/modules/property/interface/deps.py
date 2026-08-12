"""Property module wiring.

Note the **two** session scopes. Writes go through ``PropertyUow`` on the
primary; search reads go through a read-replica session and never touch the
primary at all. Search is the heaviest read in the system and must not contend
with booking transactions — a few hundred milliseconds of replication lag is
invisible on a search page and unacceptable inside a booking.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.container import Container
from app.infrastructure.database.outbox import persist_events
from app.interface.api.deps import ContainerDep
from app.modules.property.application.use_cases.calendar import (
    GetCalendarUseCase,
    GetPublicAvailabilityUseCase,
    SetAvailabilityUseCase,
    SetRatesUseCase,
)
from app.modules.property.application.use_cases.manage import (
    ChangeVisibilityUseCase,
    CreatePropertyUseCase,
    DeletePropertyUseCase,
    GetPropertyUseCase,
    GetVendorPropertyUseCase,
    ReviewPropertyUseCase,
    SubmitForReviewUseCase,
    UpdatePropertyUseCase,
)
from app.modules.property.application.use_cases.media import (
    ConfirmImagesUseCase,
    DeleteImageUseCase,
    ReorderImagesUseCase,
    RequestImageUploadUseCase,
)
from app.modules.property.application.use_cases.quote import QuoteStayUseCase
from app.modules.property.application.use_cases.rooms import (
    AddRoomTypeUseCase,
    RemoveRoomTypeUseCase,
    UpdateRoomTypeUseCase,
)
from app.modules.property.application.use_cases.search import (
    SearchPropertiesUseCase,
    SuggestUseCase,
)
from app.modules.property.infrastructure.repositories import (
    CdnImageUrlBuilder,
    SqlAmenityCatalog,
    SqlCalendarRepository,
    SqlPropertyRepository,
)
from app.modules.property.infrastructure.search_repository import SqlSearchRepository


class PropertyUow:
    """Write scope: repositories plus the outbox drain."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.properties = SqlPropertyRepository(session)
        self.calendar = SqlCalendarRepository(session)
        self.amenities = SqlAmenityCatalog(session)

    async def flush(self) -> None:
        await self.properties.flush()
        # Events land in the same transaction as the state change — the whole
        # point of the outbox.
        await persist_events(self.session, self.properties.pending_events())


async def get_property_uow(container: ContainerDep) -> AsyncIterator[PropertyUow]:
    async with container.database.write_session() as session:
        uow = PropertyUow(session)
        yield uow
        await uow.flush()


async def get_read_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    """Replica session for search. Never used for anything a write depends on."""
    async with container.database.read_session() as session:
        yield session


PropUow = Annotated[PropertyUow, Depends(get_property_uow)]
ReadSession = Annotated[AsyncSession, Depends(get_read_session)]


def _urls(container: Container) -> CdnImageUrlBuilder:
    """Listing photos are public and CDN-served, deliberately not presigned —
    a per-user signed URL would make every image a CDN miss."""
    storage = container.settings.storage
    base = storage.endpoint_url or f"https://{storage.bucket}.s3.{storage.region}.amazonaws.com"
    return CdnImageUrlBuilder(f"{base}/{storage.bucket}" if storage.endpoint_url else base)


# ══════════════════════════════════════════════════════════════════════════
# Use-case providers
# ══════════════════════════════════════════════════════════════════════════


def create_property_uc(container: ContainerDep, uow: PropUow) -> CreatePropertyUseCase:
    return CreatePropertyUseCase(
        properties=uow.properties, urls=_urls(container), clock=container.clock
    )


def update_property_uc(container: ContainerDep, uow: PropUow) -> UpdatePropertyUseCase:
    return UpdatePropertyUseCase(
        properties=uow.properties,
        amenities=uow.amenities,
        urls=_urls(container),
        clock=container.clock,
    )


def get_property_uc(container: ContainerDep, uow: PropUow) -> GetPropertyUseCase:
    return GetPropertyUseCase(properties=uow.properties, urls=_urls(container))


def get_vendor_property_uc(container: ContainerDep, uow: PropUow) -> GetVendorPropertyUseCase:
    return GetVendorPropertyUseCase(properties=uow.properties, urls=_urls(container))


def submit_for_review_uc(container: ContainerDep, uow: PropUow) -> SubmitForReviewUseCase:
    return SubmitForReviewUseCase(properties=uow.properties, urls=_urls(container))


def review_property_uc(container: ContainerDep, uow: PropUow) -> ReviewPropertyUseCase:
    return ReviewPropertyUseCase(
        properties=uow.properties, urls=_urls(container), clock=container.clock
    )


def change_visibility_uc(container: ContainerDep, uow: PropUow) -> ChangeVisibilityUseCase:
    return ChangeVisibilityUseCase(properties=uow.properties, urls=_urls(container))


def delete_property_uc(uow: PropUow) -> DeletePropertyUseCase:
    return DeletePropertyUseCase(properties=uow.properties)


def add_room_uc(uow: PropUow) -> AddRoomTypeUseCase:
    return AddRoomTypeUseCase(properties=uow.properties, amenities=uow.amenities)


def update_room_uc(container: ContainerDep, uow: PropUow) -> UpdateRoomTypeUseCase:
    return UpdateRoomTypeUseCase(
        properties=uow.properties,
        calendar=uow.calendar,
        amenities=uow.amenities,
        clock=container.clock,
    )


def remove_room_uc(uow: PropUow) -> RemoveRoomTypeUseCase:
    return RemoveRoomTypeUseCase(properties=uow.properties)


def request_upload_uc(container: ContainerDep, uow: PropUow) -> RequestImageUploadUseCase:
    return RequestImageUploadUseCase(properties=uow.properties, storage=container.storage)


def confirm_images_uc(container: ContainerDep, uow: PropUow) -> ConfirmImagesUseCase:
    return ConfirmImagesUseCase(
        properties=uow.properties, storage=container.storage, urls=_urls(container)
    )


def delete_image_uc(uow: PropUow) -> DeleteImageUseCase:
    return DeleteImageUseCase(properties=uow.properties)


def reorder_images_uc(container: ContainerDep, uow: PropUow) -> ReorderImagesUseCase:
    return ReorderImagesUseCase(properties=uow.properties, urls=_urls(container))


def get_calendar_uc(container: ContainerDep, uow: PropUow) -> GetCalendarUseCase:
    return GetCalendarUseCase(
        properties=uow.properties, calendar=uow.calendar, clock=container.clock
    )


def set_rates_uc(container: ContainerDep, uow: PropUow) -> SetRatesUseCase:
    return SetRatesUseCase(properties=uow.properties, calendar=uow.calendar, clock=container.clock)


def set_availability_uc(container: ContainerDep, uow: PropUow) -> SetAvailabilityUseCase:
    return SetAvailabilityUseCase(
        properties=uow.properties, calendar=uow.calendar, clock=container.clock
    )


def public_availability_uc(container: ContainerDep, uow: PropUow) -> GetPublicAvailabilityUseCase:
    return GetPublicAvailabilityUseCase(
        properties=uow.properties, calendar=uow.calendar, clock=container.clock
    )


def quote_uc(container: ContainerDep, uow: PropUow) -> QuoteStayUseCase:
    return QuoteStayUseCase(properties=uow.properties, calendar=uow.calendar, clock=container.clock)


def search_uc(container: ContainerDep, session: ReadSession) -> SearchPropertiesUseCase:
    """Replica-backed. See the module docstring."""
    return SearchPropertiesUseCase(
        search=SqlSearchRepository(session), cache=container.cache, clock=container.clock
    )


def suggest_uc(session: ReadSession) -> SuggestUseCase:
    return SuggestUseCase(search=SqlSearchRepository(session))


def amenity_catalog(session: ReadSession) -> SqlAmenityCatalog:
    return SqlAmenityCatalog(session)


def url_builder(container: ContainerDep) -> CdnImageUrlBuilder:
    return _urls(container)


UrlsDep = Annotated[CdnImageUrlBuilder, Depends(url_builder)]
