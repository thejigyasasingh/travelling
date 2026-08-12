"""Wishlist rules.

Small module, and the tests are about the two decisions that are easy to get
wrong and impossible to notice afterwards.

**Nothing display-shaped is stored.** A wishlist that shows the price from the
month it was saved misleads someone into clicking, and the bug is invisible
until a guest complains that a place "went up" when it never did. Every test
here that touches a price asserts it came from the catalogue on this call.

**A delisted listing is a tombstone, not a deletion.** A list that quietly gets
shorter reads as a bug, and the guest goes looking for the place they lost.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.modules.property.public.contract import PropertyCard
from app.modules.wishlist.application.dto import WishlistRow
from app.modules.wishlist.application.use_cases import (
    MAX_ITEMS,
    MAX_MERGE,
    ClearWishlist,
    ListWishlist,
    MergeWishlist,
    RemoveFromWishlist,
    SaveProperty,
)
from app.modules.wishlist.domain import errors

pytestmark = pytest.mark.unit
anyio = pytest.mark.asyncio

USER = uuid.uuid4()
NOW = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)


def card(
    property_id: uuid.UUID,
    *,
    name: str = "The Anjuna House",
    live: bool = True,
    price: int | None = 450_000,
) -> PropertyCard:
    return PropertyCard(
        id=property_id,
        slug="the-anjuna-house",
        name=name,
        city="Anjuna",
        country_code="IN",
        currency="INR",
        cover_image_url="https://cdn.example/img.jpg",
        from_price_minor=price,
        review_average=4.6,
        review_count=80,
        is_live=live,
    )


class FakeCatalog:
    def __init__(self, cards: dict[uuid.UUID, PropertyCard] | None = None) -> None:
        self._cards = cards or {}
        self.calls: list[list[uuid.UUID]] = []

    async def cards(self, property_ids):  # type: ignore[no-untyped-def]
        self.calls.append(list(property_ids))
        return {pid: self._cards[pid] for pid in property_ids if pid in self._cards}

    async def snapshot(self, property_id):  # type: ignore[no-untyped-def]
        return None

    async def rate_overrides(self, room_type_id, span):  # type: ignore[no-untyped-def]
        return {}


class FakeItems:
    def __init__(self, rows: list[WishlistRow] | None = None) -> None:
        self.rows = rows or []
        self.saved: list[tuple[uuid.UUID, str | None, str]] = []
        self.removed: list[uuid.UUID] = []

    async def list_for(self, user_id: uuid.UUID) -> list[WishlistRow]:
        return self.rows

    async def count_for(self, user_id: uuid.UUID) -> int:
        return len(self.rows)

    async def exists(self, user_id: uuid.UUID, property_id: uuid.UUID) -> bool:
        return any(r.property_id == property_id for r in self.rows)

    async def save(self, *, user_id, property_id, note, name_snapshot) -> None:  # type: ignore[no-untyped-def]
        self.saved.append((property_id, note, name_snapshot))
        if not await self.exists(user_id, property_id):
            self.rows.append(
                WishlistRow(
                    property_id=property_id,
                    name_snapshot=name_snapshot,
                    note=note,
                    created_at=NOW,
                )
            )

    async def remove(self, user_id: uuid.UUID, property_id: uuid.UUID) -> bool:
        self.removed.append(property_id)
        before = len(self.rows)
        self.rows = [r for r in self.rows if r.property_id != property_id]
        return len(self.rows) < before

    async def clear(self, user_id: uuid.UUID) -> int:
        count = len(self.rows)
        self.rows = []
        return count


def row(property_id: uuid.UUID, *, name: str = "Saved As This") -> WishlistRow:
    return WishlistRow(property_id=property_id, name_snapshot=name, note=None, created_at=NOW)


# ══════════════════════════════════════════════════════════════════════════
# Reading — live data, never stored data
# ══════════════════════════════════════════════════════════════════════════


@anyio
async def test_price_and_rating_come_from_the_catalogue() -> None:
    """**The** rule. Nothing price-shaped is ever read from the saved row."""
    pid = uuid.uuid4()
    catalog = FakeCatalog({pid: card(pid, price=999_00)})
    saved = await ListWishlist(items=FakeItems([row(pid)]), catalog=catalog).execute(USER)

    assert saved[0].from_price_minor == 999_00
    assert saved[0].review_average == 4.6
    assert catalog.calls == [[pid]], "the catalogue must be consulted, not the stored row"


@anyio
async def test_the_catalogue_is_read_once_for_the_whole_list() -> None:
    """One batch call, not one per saved property. A twenty-item wishlist is a
    normal wishlist and twenty round trips is not a normal page load."""
    pids = [uuid.uuid4() for _ in range(20)]
    catalog = FakeCatalog({pid: card(pid) for pid in pids})
    await ListWishlist(items=FakeItems([row(p) for p in pids]), catalog=catalog).execute(USER)

    assert len(catalog.calls) == 1
    assert len(catalog.calls[0]) == 20


@anyio
async def test_an_empty_list_makes_no_catalogue_call() -> None:
    catalog = FakeCatalog()
    assert await ListWishlist(items=FakeItems([]), catalog=catalog).execute(USER) == []
    assert catalog.calls == []


@anyio
async def test_a_delisted_property_stays_on_the_list() -> None:
    """A list that silently gets shorter reads as a bug, and the guest goes
    looking for the place they lost."""
    pid = uuid.uuid4()
    catalog = FakeCatalog({pid: card(pid, live=False)})
    saved = await ListWishlist(items=FakeItems([row(pid)]), catalog=catalog).execute(USER)

    assert len(saved) == 1
    assert saved[0].available is False


@anyio
async def test_a_delisted_property_carries_no_price() -> None:
    """A price on something nobody can book is an invitation to a support
    ticket about why the button does not work."""
    pid = uuid.uuid4()
    catalog = FakeCatalog({pid: card(pid, live=False, price=450_000)})
    saved = await ListWishlist(items=FakeItems([row(pid)]), catalog=catalog).execute(USER)

    assert saved[0].from_price_minor is None


@anyio
async def test_a_delisted_property_uses_the_name_the_guest_saw() -> None:
    """The tombstone column's entire reason for existing.

    A host renaming a listing after taking it down would otherwise leave the
    guest looking at a name they have never seen.
    """
    pid = uuid.uuid4()
    catalog = FakeCatalog({pid: card(pid, name="Renamed After Delisting", live=False)})
    saved = await ListWishlist(
        items=FakeItems([row(pid, name="The Name I Saved")]), catalog=catalog
    ).execute(USER)

    assert saved[0].name == "The Name I Saved"


@anyio
async def test_a_live_property_uses_its_current_name() -> None:
    """The other direction: a rename on a live listing must show through, or
    the wishlist is quietly stale."""
    pid = uuid.uuid4()
    catalog = FakeCatalog({pid: card(pid, name="Current Name", live=True)})
    saved = await ListWishlist(
        items=FakeItems([row(pid, name="Stale Snapshot")]), catalog=catalog
    ).execute(USER)

    assert saved[0].name == "Current Name"


@anyio
async def test_a_hard_deleted_property_is_dropped() -> None:
    """No card at all means there is genuinely nothing left to render — unlike
    a delisting, where the listing still exists."""
    pid = uuid.uuid4()
    saved = await ListWishlist(items=FakeItems([row(pid)]), catalog=FakeCatalog()).execute(USER)
    assert saved == []


# ══════════════════════════════════════════════════════════════════════════
# Saving
# ══════════════════════════════════════════════════════════════════════════


@anyio
async def test_saving_twice_is_one_save() -> None:
    """A heart icon is a control people press twice on a slow connection."""
    pid = uuid.uuid4()
    items = FakeItems()
    use_case = SaveProperty(items=items, catalog=FakeCatalog({pid: card(pid)}))

    await use_case.execute(USER, pid)
    await use_case.execute(USER, pid, note="second thoughts")

    assert len(items.rows) == 1


@anyio
async def test_a_delisted_property_cannot_be_newly_saved() -> None:
    """404 rather than 403, and the message does not distinguish "unpublished"
    from "never existed" — either answer enumerates listings a host has taken
    down."""
    pid = uuid.uuid4()
    use_case = SaveProperty(items=FakeItems(), catalog=FakeCatalog({pid: card(pid, live=False)}))

    with pytest.raises(errors.PropertyNotSavableError):
        await use_case.execute(USER, pid)


@anyio
async def test_an_unknown_property_cannot_be_saved() -> None:
    use_case = SaveProperty(items=FakeItems(), catalog=FakeCatalog())
    with pytest.raises(errors.PropertyNotSavableError):
        await use_case.execute(USER, uuid.uuid4())


@anyio
async def test_the_name_snapshot_is_taken_from_the_catalogue() -> None:
    """Not from the client. A caller-supplied name is a caller-supplied
    tombstone, and the tombstone is what a guest reads."""
    pid = uuid.uuid4()
    items = FakeItems()
    await SaveProperty(
        items=items, catalog=FakeCatalog({pid: card(pid, name="Real Catalogue Name")})
    ).execute(USER, pid)

    assert items.saved[0][2] == "Real Catalogue Name"


@anyio
async def test_a_blank_note_is_stored_as_null() -> None:
    """An empty string and "no note" are the same thing to a reader, and two
    representations of one state is two code paths in every consumer."""
    pid = uuid.uuid4()
    items = FakeItems()
    await SaveProperty(items=items, catalog=FakeCatalog({pid: card(pid)})).execute(
        USER, pid, note="   "
    )

    assert items.saved[0][1] is None


@anyio
async def test_the_list_is_capped() -> None:
    pid = uuid.uuid4()
    items = FakeItems([row(uuid.uuid4()) for _ in range(MAX_ITEMS)])

    with pytest.raises(errors.WishlistFullError):
        await SaveProperty(items=items, catalog=FakeCatalog({pid: card(pid)})).execute(USER, pid)


@anyio
async def test_a_full_list_can_still_have_its_notes_edited() -> None:
    """The cap is on *adding*. Re-saving something already there is a note
    edit, and refusing it would strand a full wishlist as read-only."""
    pid = uuid.uuid4()
    items = FakeItems([row(pid), *(row(uuid.uuid4()) for _ in range(MAX_ITEMS - 1))])

    await SaveProperty(items=items, catalog=FakeCatalog({pid: card(pid)})).execute(
        USER, pid, note="still editable"
    )
    assert items.saved[-1][1] == "still editable"


# ══════════════════════════════════════════════════════════════════════════
# Removing
# ══════════════════════════════════════════════════════════════════════════


@anyio
async def test_removing_something_absent_is_not_an_error() -> None:
    """Un-hearting something already gone is the guest getting what they
    wanted. An error toast for a successful no-op is worse than nothing."""
    await RemoveFromWishlist(items=FakeItems()).execute(USER, uuid.uuid4())


@anyio
async def test_clear_reports_how_many_went() -> None:
    items = FakeItems([row(uuid.uuid4()) for _ in range(3)])
    assert await ClearWishlist(items=items).execute(USER) == 3
    assert items.rows == []


# ══════════════════════════════════════════════════════════════════════════
# Merging at sign-in
# ══════════════════════════════════════════════════════════════════════════


@anyio
async def test_merge_adopts_a_devices_saves() -> None:
    """Without this, signing in loses the list a guest built while browsing —
    worse than the device-local behaviour it replaces."""
    pids = [uuid.uuid4(), uuid.uuid4()]
    items = FakeItems()
    merged = await MergeWishlist(
        items=items, catalog=FakeCatalog({p: card(p) for p in pids})
    ).execute(USER, pids)

    assert merged == 2


@anyio
async def test_merge_is_additive_and_never_removes() -> None:
    existing, incoming = uuid.uuid4(), uuid.uuid4()
    items = FakeItems([row(existing)])
    await MergeWishlist(items=items, catalog=FakeCatalog({incoming: card(incoming)})).execute(
        USER, [incoming]
    )

    assert {r.property_id for r in items.rows} == {existing, incoming}


@anyio
async def test_replaying_a_merge_changes_nothing() -> None:
    """The client fires this once at sign-in and may retry after a timeout that
    actually succeeded."""
    pid = uuid.uuid4()
    items = FakeItems()
    use_case = MergeWishlist(items=items, catalog=FakeCatalog({pid: card(pid)}))

    assert await use_case.execute(USER, [pid]) == 1
    assert await use_case.execute(USER, [pid]) == 0
    assert len(items.rows) == 1


@anyio
async def test_one_stale_id_does_not_fail_the_whole_merge() -> None:
    """A device's local list can easily hold something delisted months ago.
    Refusing the merge over it would lose the other nineteen."""
    good, gone = uuid.uuid4(), uuid.uuid4()
    items = FakeItems()
    merged = await MergeWishlist(items=items, catalog=FakeCatalog({good: card(good)})).execute(
        USER, [gone, good]
    )

    assert merged == 1
    assert [r.property_id for r in items.rows] == [good]


@anyio
async def test_merge_is_bounded() -> None:
    """The request arrives from a client that has just authenticated, and an
    unbounded id list is a free bulk-existence oracle."""
    pids = [uuid.uuid4() for _ in range(MAX_MERGE + 25)]
    items = FakeItems()
    catalog = FakeCatalog({p: card(p) for p in pids})

    await MergeWishlist(items=items, catalog=catalog).execute(USER, pids)
    assert len(catalog.calls[0]) == MAX_MERGE


@anyio
async def test_merge_respects_the_cap() -> None:
    room_for = 3
    existing = [row(uuid.uuid4()) for _ in range(MAX_ITEMS - room_for)]
    incoming = [uuid.uuid4() for _ in range(10)]
    items = FakeItems(existing)

    merged = await MergeWishlist(
        items=items, catalog=FakeCatalog({p: card(p) for p in incoming})
    ).execute(USER, incoming)

    assert merged == room_for


@anyio
async def test_merging_nothing_is_free() -> None:
    catalog = FakeCatalog()
    assert await MergeWishlist(items=FakeItems(), catalog=catalog).execute(USER, []) == 0
    assert catalog.calls == []
