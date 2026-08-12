"""Listing lifecycle: create, update, submit, review, unpublish, delete.

Every write here is vendor-scoped three times over — the route checks the
permission, the repository scopes its query by vendor id, and the aggregate
re-asserts ownership. That is not paranoia: multi-tenant data leaks almost
always come from one code path that skipped the check, and the only defence
that survives a future refactor is having the check in the layer that owns the
data.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.clock import Clock
from app.core.logging import get_logger
from app.modules.property.application.dto import (
    CreatePropertyInput,
    PropertyView,
    ReviewPropertyInput,
    UpdatePropertyInput,
)
from app.modules.property.application.ports import (
    AmenityCatalog,
    ImageUrlBuilder,
    PropertyRepository,
)
from app.modules.property.application.views import to_property_view
from app.modules.property.domain import errors
from app.modules.property.domain.entities import Property
from app.modules.property.domain.value_objects import (
    Address,
    CancellationPolicy,
    GeoPoint,
    PropertyStatus,
    PropertyType,
    slugify,
)
from app.shared.application.use_case import Actor
from app.shared.domain.errors import EntityNotFoundError

logger = get_logger(__name__)


@dataclass(slots=True)
class CreatePropertyUseCase:
    properties: PropertyRepository
    urls: ImageUrlBuilder
    clock: Clock

    async def execute(self, data: CreatePropertyInput, actor: Actor) -> PropertyView:
        """Start a draft.

        Almost nothing is required — see :meth:`Property.draft`. Completeness
        is demanded at submission, when the vendor is asking us for something,
        not at the first screen where demanding it kills onboarding.
        """
        if actor.vendor_id is None:
            raise errors.VendorScopeError

        address = Address.parse(
            line1=data.line1,
            line2=data.line2,
            city=data.city,
            state=data.state,
            country_code=data.country_code,
            postal_code=data.postal_code,
            landmark=data.landmark,
        )
        location = (
            GeoPoint(data.latitude, data.longitude)
            if data.latitude is not None and data.longitude is not None
            else None
        )

        prop = Property.draft(
            vendor_id=actor.vendor_id,
            name=data.name,
            property_type=PropertyType(data.property_type),
            address=address,
            location=location,
            description=data.description,
            currency=data.currency,
            city_id=data.city_id,
        )
        prop.slug = await self._unique_slug(prop.slug)
        await self.properties.add(prop)

        logger.info(
            "property_created",
            property_id=str(prop.id),
            vendor_id=str(actor.vendor_id),
            property_type=prop.property_type.value,
        )
        return to_property_view(prop, urls=self.urls, include_private=True)

    async def _unique_slug(self, base: str) -> str:
        """Slugs are unique platform-wide, so "Taj Palace" in Mumbai and in
        Jaipur cannot collide. Disambiguated with a short suffix rather than a
        counter, which would leak how many similarly named listings exist."""
        if not await self.properties.slug_exists(base):
            return base
        for _ in range(5):
            candidate = f"{base}-{uuid.uuid4().hex[:6]}"
            if not await self.properties.slug_exists(candidate):
                return candidate
        return f"{base}-{uuid.uuid4().hex[:12]}"  # pragma: no cover — astronomically unlikely


@dataclass(slots=True)
class UpdatePropertyUseCase:
    properties: PropertyRepository
    amenities: AmenityCatalog
    urls: ImageUrlBuilder
    clock: Clock

    async def execute(self, data: UpdatePropertyInput, actor: Actor) -> PropertyView:
        prop = await self._load(data.property_id, actor)

        if data.amenity_codes is not None:
            # Validated against the catalogue before anything is written, so a
            # typo'd code fails the request rather than creating a filter
            # nobody can ever select.
            await self.amenities.validate(frozenset(data.amenity_codes))

        address = self._merge_address(prop, data)
        location = (
            GeoPoint(data.latitude, data.longitude)
            if data.latitude is not None and data.longitude is not None
            else None
        )

        changed = prop.update_details(
            name=data.name,
            description=data.description,
            address=address,
            location=location,
            amenity_codes=frozenset(data.amenity_codes) if data.amenity_codes is not None else None,
            cancellation_policy=(
                CancellationPolicy(data.cancellation_policy) if data.cancellation_policy else None
            ),
            check_in_from=data.check_in_from,
            check_out_by=data.check_out_by,
            house_rules=data.house_rules,
            instant_booking=data.instant_booking,
            city_id=data.city_id,
        )

        logger.info("property_updated", property_id=str(prop.id), changed=changed)
        return to_property_view(prop, urls=self.urls, include_private=True)

    @staticmethod
    def _merge_address(prop: Property, data: UpdatePropertyInput) -> Address | None:
        """Address fields arrive individually but the value object is whole.

        Merged against the current address so a request that only changes the
        postal code does not blank out the street — which is what constructing
        a fresh Address from the request alone would do.
        """
        fields = (
            data.line1,
            data.line2,
            data.city,
            data.state,
            data.country_code,
            data.postal_code,
            data.landmark,
        )
        if all(f is None for f in fields):
            return None
        current = prop.address
        return Address.parse(
            line1=data.line1 if data.line1 is not None else current.line1,
            line2=data.line2 if data.line2 is not None else current.line2,
            city=data.city if data.city is not None else current.city,
            state=data.state if data.state is not None else current.state,
            country_code=(
                data.country_code if data.country_code is not None else current.country_code
            ),
            postal_code=(data.postal_code if data.postal_code is not None else current.postal_code),
            landmark=data.landmark if data.landmark is not None else current.landmark,
        )

    async def _load(self, property_id: uuid.UUID, actor: Actor) -> Property:
        prop = await self.properties.get_for_vendor(
            property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", property_id)
        prop.assert_owned_by(actor.vendor_id)
        return prop


@dataclass(slots=True)
class SubmitForReviewUseCase:
    properties: PropertyRepository
    urls: ImageUrlBuilder

    async def execute(self, property_id: uuid.UUID, actor: Actor) -> PropertyView:
        """Ask for the listing to go live.

        Raises with **every** unmet requirement at once — a vendor fixing one,
        resubmitting, and being told about the next is how half-finished
        listings get abandoned.
        """
        prop = await self.properties.get_for_vendor(
            property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", property_id)
        prop.assert_owned_by(actor.vendor_id)

        prop.submit_for_review()
        logger.info("property_submitted_for_review", property_id=str(prop.id))
        return to_property_view(prop, urls=self.urls, include_private=True)


@dataclass(slots=True)
class ReviewPropertyUseCase:
    """Admin approval or rejection. Requires ``property:publish:any``."""

    properties: PropertyRepository
    urls: ImageUrlBuilder
    clock: Clock

    async def execute(self, data: ReviewPropertyInput, actor: Actor) -> PropertyView:
        prop = await self.properties.get(data.property_id)
        if prop is None:
            raise EntityNotFoundError("Property", data.property_id)

        if data.approve:
            # Re-checks completeness: the listing is editable while it sits in
            # the queue, so what passed at submission may no longer hold.
            prop.approve(now=self.clock.now(), by=actor.user_id)
            logger.info("property_approved", property_id=str(prop.id), by=str(actor.user_id))
        else:
            reason = (data.reason or "").strip()
            if not reason:
                # A rejection with no reason is one the vendor cannot act on,
                # so the listing never gets fixed and the inventory is lost.
                msg = "A rejection reason is required"
                raise errors.SearchWindowError(msg)
            prop.reject(reason=reason, by=actor.user_id)
            logger.info("property_rejected", property_id=str(prop.id), reason=reason)

        return to_property_view(prop, urls=self.urls, include_private=True)


@dataclass(slots=True)
class ChangeVisibilityUseCase:
    """Publish, unpublish or (admin) suspend."""

    properties: PropertyRepository
    urls: ImageUrlBuilder

    async def execute(self, args: tuple[uuid.UUID, str, str | None], actor: Actor) -> PropertyView:
        property_id, action, reason = args

        if action == "suspend":
            # Admin-only. Scoped by permission at the route; loaded unscoped
            # here because an admin acts across vendors by definition.
            prop = await self.properties.get(property_id)
        else:
            prop = await self.properties.get_for_vendor(
                property_id, actor.vendor_id or uuid.UUID(int=0)
            )
        if prop is None:
            raise EntityNotFoundError("Property", property_id)

        match action:
            case "publish":
                prop.assert_owned_by(actor.vendor_id)
                if prop.status is PropertyStatus.UNPUBLISHED:
                    # Already vetted; no second review queue trip.
                    prop.republish()
                else:
                    prop.submit_for_review()
            case "unpublish":
                prop.assert_owned_by(actor.vendor_id)
                prop.unpublish(reason=reason or "vendor_request")
            case "suspend":
                prop.suspend(reason=reason or "policy_violation", by=actor.user_id)
            case _:  # pragma: no cover — the route constrains this
                msg = f"Unknown visibility action {action!r}"
                raise ValueError(msg)

        logger.info("property_visibility_changed", property_id=str(prop.id), action=action)
        return to_property_view(prop, urls=self.urls, include_private=True)


@dataclass(slots=True)
class DeletePropertyUseCase:
    properties: PropertyRepository

    async def execute(self, property_id: uuid.UUID, actor: Actor) -> None:
        """Soft delete.

        Never a hard delete: bookings, payouts, invoices and reviews reference
        this property for years, and tax law requires those records to remain
        reconstructable. The row leaves search and every vendor view; it does
        not leave the database.

        A published listing must be unpublished first — deleting live inventory
        out from under in-flight searches is how a guest ends up on a 404 from
        their own search results.
        """
        prop = await self.properties.get_for_vendor(
            property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", property_id)
        prop.assert_owned_by(actor.vendor_id)

        if prop.status is PropertyStatus.PUBLISHED:
            raise errors.InvalidStatusTransitionError(prop.status.value, "deleted")

        await self.properties.soft_delete(prop, by=actor.user_id)
        logger.info("property_deleted", property_id=str(prop.id), vendor_id=str(prop.vendor_id))


@dataclass(slots=True)
class GetPropertyUseCase:
    """Public detail page.

    Published listings only, and the exact location is withheld — see
    :meth:`GeoPoint.obfuscated`. A vendor viewing their own draft goes through
    the vendor route, which uses a different scope.
    """

    properties: PropertyRepository
    urls: ImageUrlBuilder

    async def execute(self, identifier: str, actor: Actor) -> PropertyView:
        prop = (
            await self.properties.get_by_slug(identifier)
            if not _looks_like_uuid(identifier)
            else await self.properties.get_published(uuid.UUID(identifier))
        )
        if prop is None or not prop.status.is_visible:
            raise EntityNotFoundError("Property", identifier)
        return to_property_view(prop, urls=self.urls, include_private=False)


@dataclass(slots=True)
class GetVendorPropertyUseCase:
    properties: PropertyRepository
    urls: ImageUrlBuilder

    async def execute(self, property_id: uuid.UUID, actor: Actor) -> PropertyView:
        prop = await self.properties.get_for_vendor(
            property_id, actor.vendor_id or uuid.UUID(int=0)
        )
        if prop is None:
            raise EntityNotFoundError("Property", property_id)
        return to_property_view(prop, urls=self.urls, include_private=True)


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def unique_slug_base(name: str) -> str:
    return slugify(name)
