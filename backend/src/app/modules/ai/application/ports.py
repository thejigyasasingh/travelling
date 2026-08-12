"""What the AI use cases need from the outside world.

Two ports and nothing else. The provider is behind :class:`LanguageModel`, so
swapping it, stubbing it in a test, or running two side by side is a
construction change rather than an edit to six use cases — and, more to the
point, so a test can assert what the *prompt* did without a network.

:class:`CandidateSource` is the retrieval seam. Today it is SQL over bookings
and properties; when there is a vector index it becomes a second
implementation, and no use case changes. Retrieval is the part of a
recommendation system that gets replaced most often, so it is the part most
worth isolating.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, Protocol

from app.modules.ai.domain.value_objects import Candidate


class LanguageModel(Protocol):
    """A model that answers in a fixed shape.

    Only structured calls are exposed. There is no "give me some text" method,
    because every use here puts the output in front of a guest or into a
    database column, and free text at that boundary is how a refusal
    ("I can't help with that") ends up rendered as a hotel description.
    """

    async def structured(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        tool_name: str,
        max_tokens: int | None = None,
        fast: bool = False,
    ) -> dict[str, Any]:
        """Call the model and return output validated against ``schema``.

        ``fast`` selects the cheap model. Use it for classification and
        tagging; not for anything a guest reads as prose.

        Raises :class:`~app.modules.ai.domain.errors.ModelUnavailableError` on
        transport failure or timeout, and
        :class:`~app.modules.ai.domain.errors.ModelResponseInvalidError` when
        the model answers outside the schema.
        """
        ...

    async def describe_image(
        self,
        *,
        system: str,
        user: str,
        image_bytes: bytes,
        media_type: str,
        schema: dict[str, Any],
        tool_name: str,
    ) -> dict[str, Any]:
        """The same contract, with one image attached."""
        ...

    @property
    def available(self) -> bool:
        """False when the feature is off or unconfigured.

        Checked by callers *before* building an expensive prompt, and so that
        a disabled model is a quiet degradation rather than an exception in
        the request path.
        """
        ...


class CandidateSource(Protocol):
    """Retrieval. Everything here is scoped and bounded by the caller."""

    async def similar_to(self, property_id: uuid.UUID, *, limit: int) -> Sequence[Candidate]:
        """Content neighbours: same city, comparable price band, shared
        amenities, ordered by distance."""
        ...

    async def also_booked(self, property_id: uuid.UUID, *, limit: int) -> Sequence[Candidate]:
        """Properties booked by guests who also booked this one.

        Only completed and confirmed stays count — a co-occurrence of two
        abandoned carts is not a signal about either property.
        """
        ...

    async def popular_in(self, city: str, *, limit: int) -> Sequence[Candidate]:
        """The cold-start answer, and the fallback when everything else is
        empty."""
        ...

    async def from_history(self, user_id: uuid.UUID, *, limit: int) -> Sequence[Candidate]:
        """Built from where this guest has actually stayed.

        Returns nothing for a guest with no completed stays rather than
        guessing, so a first-time visitor gets an honest "popular in" instead
        of a personalisation that is really just popularity wearing a hat.
        """
        ...

    async def in_city(self, city: str, *, limit: int) -> Sequence[Candidate]:
        """Published properties in one city, for grounding an itinerary."""
        ...

    async def city_of(self, property_id: uuid.UUID) -> str:
        """The city a property is in. Used to scope the fallback rail."""
        ...

    async def cities_with_supply(self, *, limit: int = 40) -> list[str]:
        """Cities we can actually sell a stay in.

        The whitelist destination suggestions are checked against. Without it
        the model recommends somewhere lovely that we cannot book, which is an
        advert for a competitor.
        """
        ...

    async def stay_history(self, user_id: uuid.UUID, *, limit: int = 10) -> list[dict[str, Any]]:
        """Where a guest has been, and in which month.

        City and month only — this goes into a prompt sent to a third party,
        and the rule is that it carries the least that will do the job.
        """
        ...
