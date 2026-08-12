/**
 * The wishlist.
 *
 * Server-backed for a signed-in guest, so the list follows them to another
 * device. Still device-local when signed out — a visitor deciding whether to
 * make an account is exactly the person building a shortlist, and demanding
 * they register first is how you lose them. `mergeLocalInto` hands the local
 * list over at sign-in so that browsing is not wasted.
 *
 * Prices and ratings on an entry are read live from the server, never stored:
 * a wishlist quoting the price from the month it was saved is a wishlist that
 * misleads someone into clicking.
 */

export interface WishlistEntry {
  readonly propertyId: string
  readonly slug: string
  readonly name: string
  readonly city: string
  readonly coverImageUrl: string | null
  readonly fromPriceMinor: number | null
  readonly currency: string
  readonly reviewAverage: number
  readonly reviewCount: number
  readonly savedAt: string
  readonly note: string | null
  /** False when the host has taken the listing down. The card renders as a
   *  tombstone rather than disappearing — a list that silently gets shorter is
   *  a list the guest thinks is broken. Optional so a locally-saved entry,
   *  which has no way to know, defaults to available. */
  readonly available?: boolean
}

export function isSaved(entries: readonly WishlistEntry[], propertyId: string): boolean {
  return entries.some((e) => e.propertyId === propertyId)
}

/** Newest first: the thing you just saved is the thing you want to see. */
export function sortByRecent(entries: readonly WishlistEntry[]): WishlistEntry[] {
  return [...entries].sort((a, b) => b.savedAt.localeCompare(a.savedAt))
}
