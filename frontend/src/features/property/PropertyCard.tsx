/**
 * A stay, as a card.
 *
 * The price shown depends on whether the search had dates. With dates it is the
 * **total for the stay**; without, it is a nightly "from". These are labelled
 * differently and never interchanged — showing a nightly rate where a guest
 * expects a total is the oldest dark pattern in travel, and we are not doing it.
 */

import { Link } from 'react-router-dom'
import type { SearchResultItem } from '@/domain/property'
import { cancellationPolicy } from '@/domain/policies'
import { formatMinor } from '@/core/money'
import { Rating } from '@/ui/Rating'
import { Badge } from '@/ui/feedback'
import { WishlistButton } from '@/features/wishlist/WishlistButton'
import { cn } from '@/ui/cn'

export function PropertyCard({
  item,
  searchParams,
  nights,
}: {
  item: SearchResultItem
  searchParams?: string
  nights?: number
}) {
  const policy = cancellationPolicy(item.cancellationPolicy)
  const href = `/stays/${item.slug}${searchParams ? `?${searchParams}` : ''}`

  return (
    <article
      className={cn(
        'group relative overflow-hidden rounded-2xl border border-ink-100 bg-white transition-shadow hover:shadow-card',
        !item.isAvailable && 'opacity-60',
      )}
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-ink-100">
        {item.coverImageUrl ? (
          <img
            src={item.coverImageUrl}
            alt=""
            /* Decorative: the link text below already names the property, and a
               second announcement of the same name is noise. */
            loading="lazy"
            decoding="async"
            className="size-full object-cover transition-transform duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="grid size-full place-items-center text-ink-300">No photo</div>
        )}

        <div className="absolute top-3 right-3">
          <WishlistButton item={item} />
        </div>

        {item.instantBooking && (
          <div className="absolute bottom-3 left-3">
            <Badge tone="brand">Instant booking</Badge>
          </div>
        )}
        {!item.isAvailable && (
          <div className="absolute inset-0 grid place-items-center bg-white/70">
            <Badge tone="danger">Sold out for these dates</Badge>
          </div>
        )}
      </div>

      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate font-semibold text-ink-900">
              {/* The whole card is clickable via this stretched link, which
                  keeps one tab stop and one accessible name per card. */}
              <Link to={href} className="before:absolute before:inset-0">
                {item.name}
              </Link>
            </h3>
            <p className="mt-0.5 truncate text-sm text-ink-500">
              {item.city}
              {item.distanceM !== null && ` · ${(item.distanceM / 1000).toFixed(1)} km away`}
            </p>
          </div>
          <Rating value={item.reviewAverage} count={item.reviewCount} />
        </div>

        <p className="mt-2 text-xs text-ink-500">{policy.short}</p>

        <div className="mt-3 flex items-end justify-between">
          <div>
            {item.totalPriceMinor !== null ? (
              <>
                <span className="text-lg font-semibold text-ink-900">
                  {formatMinor(item.totalPriceMinor, item.currency, { compact: true })}
                </span>
                <span className="ml-1 text-xs text-ink-500">
                  total{nights ? ` · ${nights} night${nights === 1 ? '' : 's'}` : ''}
                </span>
              </>
            ) : item.fromPriceMinor !== null ? (
              <>
                <span className="text-xs text-ink-500">from </span>
                <span className="text-lg font-semibold text-ink-900">
                  {formatMinor(item.fromPriceMinor, item.currency, { compact: true })}
                </span>
                <span className="ml-1 text-xs text-ink-500">/ night</span>
              </>
            ) : (
              <span className="text-sm text-ink-500">Price on request</span>
            )}
            <p className="text-[11px] text-ink-400">Includes taxes and fees</p>
          </div>
          <span className="text-xs text-ink-400">Sleeps {item.maxOccupancy}</span>
        </div>
      </div>
    </article>
  )
}

export function PropertyCardSkeleton() {
  return (
    <div className="overflow-hidden rounded-2xl border border-ink-100">
      <div className="shimmer aspect-[4/3]" />
      <div className="space-y-2 p-4">
        <div className="shimmer h-4 w-3/4 rounded" />
        <div className="shimmer h-3 w-1/2 rounded" />
        <div className="shimmer h-5 w-1/3 rounded" />
      </div>
    </div>
  )
}
