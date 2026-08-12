import { Link } from 'react-router-dom'
import { useClearWishlist, useWishlist } from '@/application/hooks/useWishlist'
import { formatMinor } from '@/core/money'
import { formatRelative } from '@/core/dates'
import { Rating } from '@/ui/Rating'
import { Button, ButtonLink } from '@/ui/Button'
import { EmptyState, Skeleton } from '@/ui/feedback'
import { WishlistButton } from '@/features/wishlist/WishlistButton'
import type { SearchResultItem } from '@/domain/property'

/**
 * Saved stays.
 *
 * Each card renders from the snapshot stored when it was saved, so the page
 * needs no network at all. The device-local limitation is stated on the page
 * rather than hidden — a guest who saves twelve stays on their laptop and finds
 * none on their phone deserves to know why before it happens, not after.
 */
export default function WishlistPage() {
  const { data: entries, isPending } = useWishlist()
  const clear = useClearWishlist()

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink-900">Wishlist</h1>
          <p className="mt-1 text-sm text-ink-500">
            Saved on this device.{' '}
            <span className="text-ink-400">
              Syncing across devices is coming — for now, clearing your browser data clears this
              list.
            </span>
          </p>
        </div>
        {(entries?.length ?? 0) > 0 && (
          <Button variant="ghost" size="sm" onClick={() => clear.mutate()}>
            Clear all
          </Button>
        )}
      </div>

      <div className="mt-6">
        {isPending ? (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} className="h-64" />
            ))}
          </div>
        ) : (entries?.length ?? 0) === 0 ? (
          <EmptyState
            title="Nothing saved yet"
            description="Tap the heart on any stay to keep it here while you plan."
            action={<ButtonLink to="/search">Browse stays</ButtonLink>}
          />
        ) : (
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {entries?.map((entry) => {
              // `undefined` means a locally-saved entry, which has no way to
              // know. Only an explicit `false` from the server is a tombstone.
              const gone = entry.available === false
              return (
              <li key={entry.propertyId}>
                <article
                  className={
                    gone
                      ? 'relative overflow-hidden rounded-2xl border border-ink-100 bg-ink-50'
                      : 'group relative overflow-hidden rounded-2xl border border-ink-100 bg-white transition-shadow hover:shadow-card'
                  }
                >
                  <div className={gone ? 'relative aspect-[4/3] bg-ink-100 grayscale' : 'relative aspect-[4/3] bg-ink-100'}>
                    {entry.coverImageUrl ? (
                      <img
                        src={entry.coverImageUrl}
                        alt=""
                        loading="lazy"
                        className="size-full object-cover"
                      />
                    ) : (
                      <div className="grid size-full place-items-center text-ink-300">No photo</div>
                    )}
                    <div className="absolute top-3 right-3">
                      {/* The snapshot is enough to un-save; the heart takes a
                          search-shaped item, so it is adapted here. */}
                      <WishlistButton item={asSearchItem(entry)} size="sm" />
                    </div>
                  </div>
                  <div className="p-4">
                    <h2 className="truncate font-semibold text-ink-900">
                      {gone ? (
                        // No link. The listing is not there, and a link to a
                        // 404 is worse than plain text.
                        entry.name
                      ) : (
                        <Link to={`/stays/${entry.slug}`} className="before:absolute before:inset-0">
                          {entry.name}
                        </Link>
                      )}
                    </h2>
                    <p className="mt-0.5 text-sm text-ink-500">{entry.city}</p>
                    {gone ? (
                      // Said plainly, and the row stays. A wishlist that
                      // quietly gets shorter is one the guest thinks is broken,
                      // and they go looking for the place they lost.
                      <p className="mt-2 text-sm text-ink-600">
                        No longer available. The host has taken this listing down.
                      </p>
                    ) : (
                    <div className="mt-2 flex items-end justify-between">
                      <div>
                        {entry.fromPriceMinor !== null ? (
                          <>
                            <span className="text-xs text-ink-500">from </span>
                            <span className="font-semibold text-ink-900">
                              {formatMinor(entry.fromPriceMinor, entry.currency, { compact: true })}
                            </span>
                            <span className="text-xs text-ink-500"> / night</span>
                          </>
                        ) : (
                          <span className="text-sm text-ink-500">Price on request</span>
                        )}
                      </div>
                      <Rating value={entry.reviewAverage} count={entry.reviewCount} />
                    </div>
                    )}
                    {entry.note && (
                      <p className="mt-2 text-sm text-ink-600 italic">“{entry.note}”</p>
                    )}
                    <p className="mt-2 text-xs text-ink-400">Saved {formatRelative(entry.savedAt)}</p>
                  </div>
                </article>
              </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

/** The saved snapshot, shaped for the components that expect a search result. */
function asSearchItem(entry: {
  propertyId: string
  slug: string
  name: string
  city: string
  coverImageUrl: string | null
  fromPriceMinor: number | null
  currency: string
  reviewAverage: number
  reviewCount: number
}): SearchResultItem {
  return {
    id: entry.propertyId,
    slug: entry.slug,
    name: entry.name,
    propertyType: '',
    city: entry.city,
    countryCode: 'IN',
    latitude: null,
    longitude: null,
    distanceM: null,
    coverImageUrl: entry.coverImageUrl,
    reviewAverage: entry.reviewAverage,
    reviewCount: entry.reviewCount,
    amenityCodes: [],
    instantBooking: false,
    cancellationPolicy: '',
    maxOccupancy: 0,
    fromPriceMinor: entry.fromPriceMinor,
    totalPriceMinor: null,
    currency: entry.currency,
    isAvailable: true,
  }
}
