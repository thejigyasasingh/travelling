import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useFlagReview, useReplyToReview, useReviewSummary, useReviews } from '@/api/queries'
import { PageHeader } from '@/app/Shell'
import { formatDate } from '@/core/format'
import { ApiError } from '@/core/http'
import { Badge, Button, Card, Spinner, cn } from '@/ui/primitives'
import type { Review } from '@/api/types'

/**
 * What guests said, and the host's one right of reply.
 *
 * Two rules shape this whole screen, and both are stated in the UI rather than
 * only enforced in the API:
 *
 * * a reply is public, permanent and singular — there is no second reply and no
 *   edit, because a review page that becomes an argument helps nobody reading
 *   it;
 * * flagging does **not** hide a review or stop it counting. It asks a human to
 *   look. A host who believes otherwise flags everything and then reports the
 *   feature as broken.
 */
export function ReviewsPage() {
  const [params, setParams] = useSearchParams()
  const awaitingOnly = params.get('awaiting_reply') === 'true'
  const [page, setPage] = useState(1)

  const { data: summary } = useReviewSummary()
  const { data, isPending, error } = useReviews({
    ...(awaitingOnly ? { awaiting_reply: true } : {}),
    page,
    size: 20,
  })

  return (
    <>
      <PageHeader title="Reviews" description="Every review of your properties, and your replies." />

      {summary && (
        <div className="mb-4 grid gap-3 sm:grid-cols-4">
          <Stat
            label="Rating"
            value={summary.total === 0 ? '—' : summary.average.toFixed(2)}
            hint={`${summary.total} review${summary.total === 1 ? '' : 's'}`}
          />
          <Stat label="Awaiting reply" value={String(summary.awaiting_reply)} tone={summary.awaiting_reply > 0 ? 'warn' : undefined} />
          <Stat label="One or two stars" value={String(summary.critical)} tone={summary.critical > 0 ? 'bad' : undefined} />
          <div className="rounded-xl border border-ink-200 bg-white p-4">
            <p className="text-xs text-ink-500">Distribution</p>
            <div className="mt-2 space-y-1">
              {[5, 4, 3, 2, 1].map((star) => {
                const count = data?.distribution[String(star)] ?? 0
                const total = data?.total ?? 0
                return (
                  <div key={star} className="flex items-center gap-2 text-xs">
                    <span className="w-3 text-ink-500">{star}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-100">
                      <div
                        className="h-full rounded-full bg-brand-500"
                        style={{ width: total ? `${(count / total) * 100}%` : '0%' }}
                      />
                    </div>
                    <span className="w-6 text-right tabular-nums text-ink-600">{count}</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      <div className="mb-3 flex gap-2">
        <FilterTab
          active={!awaitingOnly}
          onClick={() => {
            setParams({}, { replace: true })
            setPage(1)
          }}
        >
          All
        </FilterTab>
        <FilterTab
          active={awaitingOnly}
          onClick={() => {
            setParams({ awaiting_reply: 'true' }, { replace: true })
            setPage(1)
          }}
        >
          Awaiting your reply
        </FilterTab>
      </div>

      {isPending && (
        <div className="grid place-items-center py-20">
          <Spinner />
        </div>
      )}
      {error instanceof ApiError && (
        <Card>
          <p role="alert" className="px-4 py-8 text-center text-sm text-bad-700">
            {error.message}
          </p>
        </Card>
      )}

      <div className="space-y-3">
        {data?.items.length === 0 && (
          <Card>
            <p className="px-4 py-12 text-center text-sm text-ink-500">
              {awaitingOnly ? 'Every review has a reply.' : 'No reviews yet.'}
            </p>
          </Card>
        )}
        {data?.items.map((review) => <ReviewCard key={review.id} review={review} />)}
      </div>

      {data && data.total > 20 && (
        <div className="mt-4 flex items-center justify-between text-sm text-ink-600">
          <span>
            Page {page} of {Math.max(1, Math.ceil(data.total / 20))}
          </span>
          <div className="flex gap-2">
            <Button size="sm" disabled={page === 1} onClick={() => setPage((n) => n - 1)}>
              Previous
            </Button>
            <Button
              size="sm"
              disabled={page >= Math.ceil(data.total / 20)}
              onClick={() => setPage((n) => n + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </>
  )
}

function ReviewCard({ review }: { review: Review }) {
  const reply = useReplyToReview()
  const flag = useFlagReview()
  const [replying, setReplying] = useState(false)
  const [flagging, setFlagging] = useState(false)
  const [body, setBody] = useState('')
  const [reason, setReason] = useState('')

  const removed = review.moderation === 'removed'

  return (
    <Card className={removed ? 'opacity-60' : undefined}>
      <div className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Stars rating={review.rating} />
          <span className="text-sm font-medium text-ink-900">{review.author_name}</span>
          <span className="text-xs text-ink-500">{formatDate(review.published_at)}</span>
          {review.edited_at && <span className="text-xs text-ink-400">edited</span>}
          {review.moderation === 'flagged' && <Badge tone="warn">Reported — under review</Badge>}
          {removed && <Badge tone="bad">Removed by staff</Badge>}
        </div>

        {review.title && <p className="mt-2 font-medium text-ink-900">{review.title}</p>}
        <p className="mt-1 text-sm whitespace-pre-line text-ink-700">{review.body}</p>

        {Object.keys(review.categories).length > 0 && (
          <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-500">
            {Object.entries(review.categories).map(([name, score]) => (
              <div key={name} className="flex gap-1">
                <dt className="capitalize">{name}</dt>
                <dd className="font-medium text-ink-700">{score}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>

      {review.host_reply && (
        <div className="border-t border-ink-100 bg-ink-50 px-4 py-3">
          <p className="text-xs font-medium text-ink-600">
            Your reply · {formatDate(review.host_replied_at)}
          </p>
          <p className="mt-1 text-sm whitespace-pre-line text-ink-700">{review.host_reply}</p>
        </div>
      )}

      {!removed && (
        <div className="border-t border-ink-100 px-4 py-3">
          {replying && (
            <div className="space-y-2">
              <label className="block text-sm">
                <span className="text-xs font-medium text-ink-600">
                  Your reply is public and cannot be edited or replied to again.
                </span>
                <textarea
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                  rows={3}
                  className="mt-1 w-full rounded-lg border border-ink-200 p-2 text-sm"
                  autoFocus
                />
              </label>
              <div className="flex gap-2">
                <Button
                  variant="primary"
                  disabled={reply.isPending || body.trim().length < 10}
                  onClick={() =>
                    reply.mutate(
                      { reviewId: review.id, body: body.trim() },
                      { onSuccess: () => setReplying(false) },
                    )
                  }
                >
                  {reply.isPending ? 'Posting…' : 'Post reply'}
                </Button>
                <Button onClick={() => setReplying(false)}>Cancel</Button>
              </div>
            </div>
          )}

          {flagging && (
            <div className="space-y-2">
              <p className="rounded-lg bg-ink-50 px-3 py-2 text-xs text-ink-600">
                Reporting asks our team to look. The review stays visible and keeps counting towards
                your rating while they do — it is not a way to remove criticism.
              </p>
              <label className="block text-sm">
                <span className="text-xs font-medium text-ink-600">What is wrong with it?</span>
                <input
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  className="mt-1 h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
                  autoFocus
                />
              </label>
              <div className="flex gap-2">
                <Button
                  variant="danger"
                  disabled={flag.isPending || reason.trim().length < 3}
                  onClick={() =>
                    flag.mutate(
                      { reviewId: review.id, reason: reason.trim() },
                      { onSuccess: () => setFlagging(false) },
                    )
                  }
                >
                  {flag.isPending ? 'Reporting…' : 'Report to our team'}
                </Button>
                <Button onClick={() => setFlagging(false)}>Cancel</Button>
              </div>
            </div>
          )}

          {!replying && !flagging && (
            <div className="flex flex-wrap gap-2">
              {!review.host_reply && (
                <Button variant="primary" onClick={() => setReplying(true)}>
                  Reply
                </Button>
              )}
              {review.moderation === 'published' && (
                <Button onClick={() => setFlagging(true)}>Report</Button>
              )}
            </div>
          )}

          {(reply.error ?? flag.error) instanceof ApiError && (
            <p role="alert" className="mt-2 rounded-lg bg-bad-50 px-3 py-2 text-sm text-bad-700">
              {((reply.error ?? flag.error) as ApiError).message}
            </p>
          )}
        </div>
      )}
    </Card>
  )
}

function Stars({ rating }: { rating: number }) {
  return (
    <span className="text-sm tracking-tight" aria-label={`${rating} out of 5`}>
      <span className="text-warn-500">{'★'.repeat(rating)}</span>
      <span className="text-ink-300">{'★'.repeat(5 - rating)}</span>
    </span>
  )
}

function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: string
  hint?: string | undefined
  tone?: 'warn' | 'bad' | undefined
}) {
  return (
    <div
      className={cn(
        'rounded-xl border p-4',
        tone === 'warn'
          ? 'border-warn-200 bg-warn-50'
          : tone === 'bad'
            ? 'border-bad-200 bg-bad-50'
            : 'border-ink-200 bg-white',
      )}
    >
      <p className="text-xs text-ink-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-ink-900">{value}</p>
      {hint && <p className="text-xs text-ink-500">{hint}</p>}
    </div>
  )
}

function FilterTab({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? 'rounded-lg bg-brand-50 px-3 py-1.5 text-sm font-medium text-brand-700'
          : 'rounded-lg px-3 py-1.5 text-sm text-ink-600 hover:bg-ink-100'
      }
    >
      {children}
    </button>
  )
}
