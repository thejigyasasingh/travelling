import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useSearch } from '@/application/hooks/useCatalog'
import { useSearchCriteria } from '@/application/hooks/useSearchParamsState'
import { SearchBar } from '@/features/search/SearchBar'
import { Filters } from '@/features/search/Filters'
import { PropertyCard, PropertyCardSkeleton } from '@/features/property/PropertyCard'
import type { SortOption } from '@/application/ports'
import { nightsBetween } from '@/core/dates'
import { Button } from '@/ui/Button'
import { EmptyState, ErrorState } from '@/ui/feedback'
import { Modal } from '@/ui/Modal'

const SORT_LABELS: Record<SortOption, string> = {
  relevance: 'Most relevant',
  price_asc: 'Price: low to high',
  price_desc: 'Price: high to low',
  rating_desc: 'Guest rating',
  distance_asc: 'Distance',
  newest: 'Newest',
}

/**
 * Search results.
 *
 * Filters on the left from `md` up, in a sheet below it. The result list is
 * cursor-paginated with an explicit "Show more" rather than an infinite scroll:
 * infinite scroll makes the footer unreachable and loses the guest's place when
 * they open a stay and come back.
 */
export default function SearchPage() {
  const [params] = useSearchParams()
  const { criteria, update } = useSearchCriteria()
  const [filtersOpen, setFiltersOpen] = useState(false)

  const query = useSearch(criteria)
  const items = query.data?.pages.flatMap((page) => page.items) ?? []
  const total = query.data?.pages[0]?.totalEstimate ?? null
  const nights =
    criteria.checkIn && criteria.checkOut
      ? nightsBetween(criteria.checkIn, criteria.checkOut)
      : undefined

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <SearchBar variant="compact" initial={criteria} />

      <div className="mt-6 flex items-center justify-between gap-3">
        <div aria-live="polite" className="text-sm text-ink-600">
          {query.isPending ? (
            'Searching…'
          ) : (
            <>
              <span className="font-semibold text-ink-900">
                {total !== null ? total.toLocaleString('en-IN') : items.length}
              </span>{' '}
              {items.length === 1 ? 'stay' : 'stays'}
              {criteria.q ? ` in ${criteria.q}` : ''}
              {nights ? ` · ${nights} night${nights === 1 ? '' : 's'}` : ''}
            </>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" className="md:hidden" onClick={() => setFiltersOpen(true)}>
            Filters
          </Button>
          <label className="sr-only" htmlFor="sort">
            Sort results
          </label>
          <select
            id="sort"
            value={criteria.sort ?? 'relevance'}
            onChange={(e) => update({ sort: e.target.value as SortOption })}
            className="h-9 rounded-lg border border-ink-200 bg-white px-2 text-sm"
          >
            {Object.entries(SORT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-5 grid gap-8 md:grid-cols-[260px_1fr]">
        <aside className="hidden md:block">
          <div className="sticky top-24">
            <Filters />
          </div>
        </aside>

        <div>
          {query.isError ? (
            <ErrorState error={query.error} onRetry={() => void query.refetch()} />
          ) : query.isPending ? (
            <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => (
                <PropertyCardSkeleton key={i} />
              ))}
            </div>
          ) : items.length === 0 ? (
            <EmptyState
              title="No stays match those filters"
              description="Try widening the dates, raising the price range, or removing an amenity."
              action={
                <Button variant="secondary" onClick={() => update({ amenity: [], propertyType: [], minPrice: undefined, maxPrice: undefined, minRating: undefined })}>
                  Clear filters
                </Button>
              }
            />
          ) : (
            <>
              <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                {items.map((item) => (
                  <PropertyCard
                    key={item.id}
                    item={item}
                    searchParams={params.toString()}
                    {...(nights === undefined ? {} : { nights })}
                  />
                ))}
              </div>

              {query.hasNextPage && (
                <div className="mt-8 flex justify-center">
                  <Button
                    variant="secondary"
                    loading={query.isFetchingNextPage}
                    onClick={() => void query.fetchNextPage()}
                  >
                    Show more stays
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <Modal open={filtersOpen} onClose={() => setFiltersOpen(false)} title="Filters" size="md">
        <Filters onDone={() => setFiltersOpen(false)} />
      </Modal>
    </div>
  )
}
