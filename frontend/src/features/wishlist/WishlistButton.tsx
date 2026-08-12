import { useWishlist, useToggleWishlist } from '@/application/hooks/useWishlist'
import type { SearchResultItem, Property } from '@/domain/property'
import { isSaved } from '@/domain/wishlist'
import type { WishlistEntry } from '@/domain/wishlist'
import { cn } from '@/ui/cn'

/**
 * The heart.
 *
 * It stores a **snapshot** of the card, not just an id. That is what lets the
 * Wishlist page render instantly with no N+1 fetch, and what keeps a saved stay
 * visible if the listing is later unpublished — a silently vanishing wishlist
 * is worse than a stale one clearly marked.
 */
export function WishlistButton({
  item,
  size = 'md',
}: {
  item: SearchResultItem | Property
  size?: 'sm' | 'md'
}) {
  const { data: entries = [] } = useWishlist()
  const toggle = useToggleWishlist()
  const saved = isSaved(entries, item.id)

  const entry: WishlistEntry = {
    propertyId: item.id,
    slug: item.slug,
    name: item.name,
    city: item.city,
    coverImageUrl:
      'coverImageUrl' in item ? item.coverImageUrl : (item.images[0]?.url ?? null),
    fromPriceMinor:
      'fromPriceMinor' in item
        ? item.fromPriceMinor
        : Math.min(...item.roomTypes.map((r) => r.baseRateMinor), Infinity) || null,
    currency: item.currency,
    reviewAverage: item.reviewAverage,
    reviewCount: item.reviewCount,
    savedAt: new Date().toISOString(),
    note: null,
  }

  return (
    <button
      type="button"
      onClick={(event) => {
        // Cards wrap a stretched link; without this the heart navigates.
        event.preventDefault()
        event.stopPropagation()
        toggle.mutate({ entry, saved })
      }}
      aria-pressed={saved}
      aria-label={saved ? `Remove ${item.name} from wishlist` : `Save ${item.name} to wishlist`}
      className={cn(
        'relative z-10 grid place-items-center rounded-full bg-white/90 shadow-sm backdrop-blur transition-transform hover:scale-110 active:scale-95',
        size === 'sm' ? 'size-8' : 'size-9',
      )}
    >
      <svg
        viewBox="0 0 24 24"
        className={cn(size === 'sm' ? 'size-4' : 'size-5', saved ? 'text-danger-600' : 'text-ink-500')}
        fill={saved ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth={1.8}
        aria-hidden="true"
      >
        <path d="M12 20s-7-4.4-7-9.5A4 4 0 0 1 12 7a4 4 0 0 1 7 3.5C19 15.6 12 20 12 20z" />
      </svg>
    </button>
  )
}
