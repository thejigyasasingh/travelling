import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useProperty } from '@/application/hooks/useCatalog'
import { usePropertyReviews } from '@/application/hooks/useReviews'
import { ReviewList, ReviewSummaryPanel } from '@/features/reviews/ReviewList'
import { ErrorState, LoadingBlock } from '@/ui/feedback'

/** All reviews for one property. */
export default function ReviewsPage() {
  const { slug } = useParams<{ slug: string }>()
  const [sort, setSort] = useState('recent')

  const { data: property, isPending, isError, error } = useProperty(slug)
  const reviews = usePropertyReviews(property?.id, sort)

  if (isPending) return <LoadingBlock />
  if (isError || !property) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <ErrorState error={error} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <nav aria-label="Breadcrumb" className="mb-4 text-sm text-ink-500">
        <Link to={`/stays/${property.slug}`} className="hover:text-brand-600">
          {property.name}
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-ink-700">Reviews</span>
      </nav>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold tracking-tight text-ink-900">
          Reviews of {property.name}
        </h1>
        {(reviews.data?.items.length ?? 0) > 1 && (
          <div>
            <label htmlFor="review-sort" className="sr-only">
              Sort reviews
            </label>
            <select
              id="review-sort"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className="h-9 rounded-lg border border-ink-200 px-2 text-sm"
            >
              <option value="recent">Most recent</option>
              <option value="rating_desc">Highest rated</option>
              <option value="rating_asc">Lowest rated</option>
            </select>
          </div>
        )}
      </div>

      <div className="mt-5">
        <ReviewSummaryPanel
          average={property.reviewAverage}
          count={property.reviewCount}
          summary={reviews.data?.summary}
        />
        <ReviewList reviews={reviews.data?.items ?? []} />
      </div>
    </div>
  )
}
