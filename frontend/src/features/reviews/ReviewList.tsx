import type { Review, ReviewSummary } from '@/domain/review'
import { REVIEW_CATEGORIES, ratingLabel } from '@/domain/review'
import { formatDate } from '@/core/dates'
import { Rating, StarIcon } from '@/ui/Rating'
import { EmptyState } from '@/ui/feedback'

/**
 * The rating summary.
 *
 * The average and count come from the **property**, which the backend really
 * maintains. The distribution and per-category bars come from the review
 * repository, which today has no server behind it — so they are rendered only
 * when present, and their absence is stated rather than faked.
 */
export function ReviewSummaryPanel({
  average,
  count,
  summary,
}: {
  average: number
  count: number
  summary?: ReviewSummary | undefined
}) {
  if (count === 0) {
    return (
      <div className="rounded-2xl border border-ink-100 p-5 text-sm text-ink-600">
        No reviews yet. Ratings appear once guests have stayed and reviewed.
      </div>
    )
  }

  const distribution = summary?.distribution ?? {}
  const hasDistribution = Object.keys(distribution).length > 0

  return (
    <div className="rounded-2xl border border-ink-100 p-5">
      <div className="flex flex-wrap items-center gap-6">
        <div>
          <div className="flex items-baseline gap-1.5">
            <StarIcon className="size-6 text-brand-600" />
            <span className="text-3xl font-bold text-ink-900">{average.toFixed(1)}</span>
            <span className="text-sm text-ink-500">/ 5</span>
          </div>
          <p className="mt-0.5 text-sm text-ink-600">
            {ratingLabel(average)} · {count.toLocaleString('en-IN')} review
            {count === 1 ? '' : 's'}
          </p>
        </div>

        {hasDistribution && (
          <div className="min-w-48 flex-1 space-y-1">
            {[5, 4, 3, 2, 1].map((star) => {
              const n = distribution[star] ?? 0
              const pct = count > 0 ? Math.round((n / count) * 100) : 0
              return (
                <div key={star} className="flex items-center gap-2 text-xs text-ink-500">
                  <span className="w-3 tabular-nums">{star}</span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-100">
                    <div className="h-full rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="w-8 text-right tabular-nums">{n}</span>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {summary && Object.keys(summary.categoryAverages).length > 0 && (
        <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-ink-100 pt-4 sm:grid-cols-3">
          {REVIEW_CATEGORIES.map((category) => {
            const value = summary.categoryAverages[category.key]
            if (value === undefined) return null
            return (
              <div key={category.key} className="flex items-center justify-between gap-2">
                <dt className="text-sm text-ink-600">{category.label}</dt>
                <dd className="text-sm font-medium tabular-nums text-ink-900">
                  {value.toFixed(1)}
                </dd>
              </div>
            )
          })}
        </dl>
      )}
    </div>
  )
}

export function ReviewList({ reviews, limit }: { reviews: readonly Review[]; limit?: number }) {
  const shown = limit ? reviews.slice(0, limit) : reviews

  if (shown.length === 0) {
    return (
      <div className="mt-4">
        <EmptyState
          title="No written reviews yet"
          description="Be the first to write about this place after your stay."
        />
      </div>
    )
  }

  return (
    <ul className="mt-4 space-y-5">
      {shown.map((review) => (
        <li key={review.id} className="border-b border-ink-100 pb-5 last:border-0">
          <div className="flex items-start gap-3">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
              {review.authorName.slice(0, 1).toUpperCase()}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="font-medium text-ink-900">{review.authorName}</span>
                <Rating value={review.rating} />
                <span className="text-xs text-ink-400">{formatDate(review.createdAt.slice(0, 10))}</span>
              </div>
              {review.title && <p className="mt-1 font-medium text-ink-800">{review.title}</p>}
              <p className="mt-1 whitespace-pre-line text-sm text-ink-700">{review.body}</p>

              {review.hostReply && (
                <div className="mt-3 rounded-xl bg-ink-50 p-3">
                  <p className="text-xs font-medium text-ink-700">Response from the host</p>
                  <p className="mt-1 text-sm text-ink-600">{review.hostReply.body}</p>
                </div>
              )}
            </div>
          </div>
        </li>
      ))}
    </ul>
  )
}
