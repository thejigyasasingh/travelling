/**
 * Reviews.
 *
 * These types are what the UI is written against; `infrastructure/api/reviews.ts`
 * maps the server's shapes onto them. The rules duplicated here — minimum body
 * length, the rating range — exist to fail a form before a round trip, not to
 * be the enforcement. The server re-checks every one of them, and it is the
 * server that decides.
 */

export interface Review {
  readonly id: string
  readonly propertyId: string
  readonly bookingId: string | null
  readonly authorName: string
  readonly authorAvatarUrl: string | null
  readonly rating: number
  readonly title: string | null
  readonly body: string
  readonly stayedOn: string | null
  readonly createdAt: string
  readonly categories: Readonly<Record<string, number>>
  readonly hostReply: { readonly body: string; readonly repliedAt: string } | null
}

export interface ReviewSummary {
  readonly average: number
  readonly count: number
  /** Rating (1–5) → how many reviews gave it. Drives the distribution bars. */
  readonly distribution: Readonly<Record<number, number>>
  readonly categoryAverages: Readonly<Record<string, number>>
}

export interface ReviewDraft {
  readonly bookingId: string
  readonly propertyId: string
  readonly rating: number
  readonly title: string
  readonly body: string
  readonly categories: Record<string, number>
}

export const REVIEW_CATEGORIES = [
  { key: 'cleanliness', label: 'Cleanliness' },
  { key: 'accuracy', label: 'Accuracy' },
  { key: 'location', label: 'Location' },
  { key: 'value', label: 'Value' },
  { key: 'communication', label: 'Communication' },
] as const

export const MIN_REVIEW_LENGTH = 40

export function ratingLabel(rating: number): string {
  if (rating >= 4.5) return 'Exceptional'
  if (rating >= 4.2) return 'Excellent'
  if (rating >= 3.8) return 'Very good'
  if (rating >= 3.2) return 'Good'
  if (rating > 0) return 'Fair'
  return 'New'
}

export function validateDraft(draft: ReviewDraft): string[] {
  const problems: string[] = []
  if (draft.rating < 1 || draft.rating > 5) problems.push('Choose a rating from 1 to 5 stars.')
  if (draft.body.trim().length < MIN_REVIEW_LENGTH) {
    problems.push(`Tell future guests a little more — at least ${MIN_REVIEW_LENGTH} characters.`)
  }
  return problems
}

/** Only a guest who actually stayed may review, which is what makes it worth reading. */
export function summarise(reviews: readonly Review[]): ReviewSummary {
  if (reviews.length === 0) {
    return { average: 0, count: 0, distribution: {}, categoryAverages: {} }
  }
  const distribution: Record<number, number> = {}
  const categoryTotals: Record<string, { sum: number; n: number }> = {}
  let total = 0

  for (const review of reviews) {
    total += review.rating
    const bucket = Math.round(review.rating)
    distribution[bucket] = (distribution[bucket] ?? 0) + 1
    for (const [key, value] of Object.entries(review.categories)) {
      const acc = categoryTotals[key] ?? { sum: 0, n: 0 }
      categoryTotals[key] = { sum: acc.sum + value, n: acc.n + 1 }
    }
  }

  const categoryAverages: Record<string, number> = {}
  for (const [key, { sum, n }] of Object.entries(categoryTotals)) categoryAverages[key] = sum / n

  return {
    average: total / reviews.length,
    count: reviews.length,
    distribution,
    categoryAverages,
  }
}
