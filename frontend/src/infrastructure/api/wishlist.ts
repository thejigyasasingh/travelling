/**
 * `WishlistRepository` over `/wishlist`.
 *
 * Saved places now follow the guest to another device. Two consequences of
 * that which shape this file:
 *
 * **Prices and ratings are read live, not stored.** The port's `WishlistEntry`
 * carries them because the UI renders a card, but nothing here persists them —
 * every `list()` gets today's numbers. A wishlist quoting the price from the
 * month it was saved is a wishlist that misleads someone into clicking.
 *
 * **A delisted property stays on the list, flagged.** `available: false` means
 * the host took it down; the card renders as a tombstone rather than vanishing,
 * because a list that silently gets shorter is a list the guest thinks is
 * broken.
 *
 * `localWishlistRepository` is still here, and still used — for signed-out
 * visitors, who have nowhere on the server to save anything. `mergeLocalInto`
 * is what hands that list over at sign-in, so browsing before you have an
 * account is not wasted.
 */

import type { WishlistRepository } from '@/application/ports'
import type { WishlistEntry } from '@/domain/wishlist'
import { http } from '@/infrastructure/http/client'
import { readJson, writeJson } from '@/infrastructure/storage/localStore'

const KEY = 'wishlist'

interface SavedPropertyDto {
  property_id: string
  name: string
  slug: string
  city: string
  country_code: string
  currency: string
  cover_image_url: string | null
  from_price_minor: number | null
  review_average: number
  review_count: number
  available: boolean
  note: string | null
  saved_at: string
}

function toEntry(dto: SavedPropertyDto): WishlistEntry {
  return {
    propertyId: dto.property_id,
    slug: dto.slug,
    name: dto.name,
    city: dto.city,
    coverImageUrl: dto.cover_image_url,
    fromPriceMinor: dto.from_price_minor,
    currency: dto.currency,
    reviewAverage: dto.review_average,
    reviewCount: dto.review_count,
    savedAt: dto.saved_at,
    note: dto.note,
    available: dto.available,
  }
}

export const wishlistRepository: WishlistRepository = {
  async list(): Promise<readonly WishlistEntry[]> {
    const rows = await http.get<SavedPropertyDto[]>('/wishlist')
    return rows.map(toEntry)
  },

  async add(entry: WishlistEntry): Promise<void> {
    // PUT, and only the id and note are sent. Everything else on the entry is
    // display data the server owns — sending it would let a client write its
    // own price onto a card.
    await http.put<void>(`/wishlist/${entry.propertyId}`, { note: entry.note ?? '' })
  },

  async remove(propertyId: string): Promise<void> {
    await http.delete<void>(`/wishlist/${propertyId}`)
  },

  async clear(): Promise<void> {
    await http.delete<void>('/wishlist')
  },
}

// ── signed out ────────────────────────────────────────────────────────────

/* eslint-disable @typescript-eslint/require-await -- These implement an async
   port. Dropping `async` would make the signatures diverge from the interface
   the HTTP implementation satisfies, which is the churn the port prevents. */

function stored(): WishlistEntry[] {
  return readJson<WishlistEntry[]>(KEY, [])
}

/**
 * The signed-out wishlist.
 *
 * Still device-local, because there is no account to attach it to. Worth
 * keeping rather than requiring sign-in to save: a visitor deciding whether to
 * make an account is exactly the person building a shortlist, and demanding
 * they register first is how you lose them.
 */
export const localWishlistRepository: WishlistRepository = {
  async list() {
    return stored()
  },

  async add(entry) {
    const rest = stored().filter((e) => e.propertyId !== entry.propertyId)
    writeJson(KEY, [{ ...entry, savedAt: new Date().toISOString() }, ...rest])
  },

  async remove(propertyId) {
    writeJson(
      KEY,
      stored().filter((e) => e.propertyId !== propertyId),
    )
  },

  async clear() {
    writeJson(KEY, [])
  },
}

/* eslint-enable @typescript-eslint/require-await */

/**
 * Hand the device's list to the account, once, at sign-in.
 *
 * Clears local storage only after the server confirms, so a failed merge
 * leaves the list where it was rather than losing it between the two. The
 * server is additive and idempotent, so a retry after a timeout that actually
 * succeeded costs nothing.
 */
export async function mergeLocalInto(): Promise<number> {
  const local = stored()
  if (local.length === 0) return 0

  const { merged } = await http.post<{ merged: number }>('/wishlist/merge', {
    property_ids: local.map((e) => e.propertyId).slice(0, 50),
  })
  writeJson(KEY, [])
  return merged
}
