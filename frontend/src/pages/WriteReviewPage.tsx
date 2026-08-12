import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useBooking } from '@/application/hooks/useBookings'
import { useSubmitReview } from '@/application/hooks/useReviews'
import { REVIEW_CATEGORIES, MIN_REVIEW_LENGTH, validateDraft } from '@/domain/review'
import { canReview } from '@/domain/booking'
import { formatStay } from '@/core/dates'
import { messageFor } from '@/core/errors'
import { Button } from '@/ui/Button'
import { Input, Textarea } from '@/ui/Field'
import { StarInput } from '@/ui/Rating'
import { ErrorState, LoadingBlock } from '@/ui/feedback'

/**
 * Write a review.
 *
 * Only reachable from a **completed** booking, which is the property that makes
 * a review worth reading: the author demonstrably stayed there. The guard is
 * repeated here rather than trusted from the link, because a URL is not a
 * permission.
 */
export default function WriteReviewPage() {
  const { bookingId } = useParams<{ bookingId: string }>()
  const navigate = useNavigate()
  const { data: booking, isPending, isError, error } = useBooking(bookingId)
  const submit = useSubmitReview()

  const [rating, setRating] = useState(0)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [categories, setCategories] = useState<Record<string, number>>({})
  const [problems, setProblems] = useState<string[]>([])

  if (isPending) return <LoadingBlock />
  if (isError || !booking) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <ErrorState error={error} />
      </div>
    )
  }

  if (!canReview(booking)) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center">
        <h1 className="text-xl font-semibold text-ink-900">You can review this after your stay</h1>
        <p className="mt-2 text-sm text-ink-600">
          Reviews open once the stay is complete — that is what makes them worth reading.
        </p>
        <Button className="mt-6" onClick={() => navigate(`/trips/${booking.id}`)}>
          Back to this trip
        </Button>
      </div>
    )
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!booking) return
    const draft = {
      bookingId: booking.id,
      propertyId: booking.propertyId,
      rating,
      title,
      body,
      categories,
    }
    const found = validateDraft(draft)
    setProblems(found)
    if (found.length > 0) return

    submit.mutate(draft, { onSuccess: () => void navigate(`/trips/${booking.id}`) })
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <h1 className="text-2xl font-bold tracking-tight text-ink-900">
        How was {booking.propertyName}?
      </h1>
      <p className="mt-1 text-sm text-ink-500">
        {formatStay(booking.checkIn, booking.checkOut)} · {booking.roomTypeName}
      </p>

      <p className="mt-4 rounded-xl bg-ink-50 p-4 text-sm text-ink-600">
        Your review is public and shows your first name. You can correct it for 48 hours, or until
        the host replies.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-6">
        <fieldset>
          <legend className="text-sm font-medium text-ink-700">Overall rating</legend>
          <div className="mt-2">
            <StarInput value={rating} onChange={setRating} label="Overall rating" />
          </div>
        </fieldset>

        <fieldset>
          <legend className="text-sm font-medium text-ink-700">Rate the details</legend>
          <p className="mt-0.5 text-xs text-ink-500">Optional, but the most useful part for others.</p>
          <div className="mt-3 space-y-3">
            {REVIEW_CATEGORIES.map((category) => (
              <div key={category.key} className="flex items-center justify-between gap-4">
                <span className="text-sm text-ink-700">{category.label}</span>
                <StarInput
                  value={categories[category.key] ?? 0}
                  onChange={(value) => setCategories((c) => ({ ...c, [category.key]: value }))}
                  label={category.label}
                />
              </div>
            ))}
          </div>
        </fieldset>

        <Input
          label="Headline"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={80}
          placeholder="A quiet villa five minutes from the beach"
        />

        <Textarea
          label="Your review"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={6}
          maxLength={2000}
          required
          hint={`${body.trim().length} / ${MIN_REVIEW_LENGTH} characters minimum. What would you want to have known before booking?`}
        />

        {problems.length > 0 && (
          <ul role="alert" className="space-y-1 rounded-xl bg-danger-50 p-3 text-sm text-danger-700">
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        )}

        {submit.isError && (
          <p role="alert" className="rounded-xl bg-danger-50 p-3 text-sm text-danger-700">
            {messageFor(submit.error)}
          </p>
        )}

        <div className="flex gap-3">
          <Button type="submit" size="lg" loading={submit.isPending}>
            Submit review
          </Button>
          <Button type="button" variant="ghost" size="lg" onClick={() => navigate(-1)}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  )
}
