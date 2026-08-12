/**
 * `ReviewRepository` over `/reviews`.
 *
 * Was a localStorage placeholder while the backend had no reviews module. It
 * shipped, so this is now HTTP and a guest's review is visible to other guests
 * — which is the entire point of the feature and was not true before.
 *
 * Three things the server does that this file has to respect rather than
 * paper over:
 *
 * * **Paging is offset, not cursor.** The port speaks `nextCursor` because the
 *   guest-facing lists elsewhere are unbounded; a property's reviews are not.
 *   The page number is encoded into the cursor string here so the port keeps
 *   one shape, and `null` means the last page.
 * * **A guest cannot delete a review.** Deliberate: a rating anyone can retract
 *   under pressure from a host is a rating that means nothing. `remove` is gone
 *   from the port rather than implemented as a lie.
 * * **`mine()` returns removed reviews too.** The author is the one person
 *   entitled to know theirs was taken down.
 */

import type { Page, ReviewRepository } from '@/application/ports'
import type { Review, ReviewDraft, ReviewSummary } from '@/domain/review'
import { http } from '@/infrastructure/http/client'

interface ReviewDto {
  id: string
  property_id: string
  rating: number
  title: string | null
  body: string
  categories: Record<string, number>
  author_name: string
  published_at: string
  edited_at: string | null
  host_reply: string | null
  host_replied_at: string | null
  moderation: string
  can_edit: boolean
}

interface ReviewListDto {
  items: ReviewDto[]
  total: number
  page: number
  size: number
  average: number
  distribution: Record<string, number>
}

const PAGE_SIZE = 20

function toReview(dto: ReviewDto): Review {
  return {
    id: dto.id,
    propertyId: dto.property_id,
    // The server does not return the booking a review came from on a public
    // read, and it should not: it would let anyone correlate a review with a
    // specific stay.
    bookingId: null,
    authorName: dto.author_name,
    authorAvatarUrl: null,
    rating: dto.rating,
    title: dto.title,
    body: dto.body,
    stayedOn: null,
    createdAt: dto.published_at,
    categories: dto.categories ?? {},
    hostReply:
      dto.host_reply && dto.host_replied_at
        ? { body: dto.host_reply, repliedAt: dto.host_replied_at }
        : null,
  }
}

/**
 * Category averages are computed here, from the page just fetched.
 *
 * The server aggregates the overall rating and the star distribution because
 * those drive search ranking and have to be exact across every review. Category
 * scores are optional per review and decorative on the page, so averaging the
 * visible ones is honest — and the alternative, a second aggregate table for a
 * number nobody sorts by, is not worth maintaining.
 */
function categoryAverages(reviews: readonly Review[]): Record<string, number> {
  const totals: Record<string, { sum: number; n: number }> = {}
  for (const review of reviews) {
    for (const [key, score] of Object.entries(review.categories)) {
      const bucket = (totals[key] ??= { sum: 0, n: 0 })
      bucket.sum += score
      bucket.n += 1
    }
  }
  return Object.fromEntries(
    Object.entries(totals).map(([key, { sum, n }]) => [key, Math.round((sum / n) * 10) / 10]),
  )
}

function toSummary(dto: ReviewListDto, items: readonly Review[]): ReviewSummary {
  const distribution: Record<number, number> = {}
  for (const [star, count] of Object.entries(dto.distribution ?? {})) {
    distribution[Number(star)] = count
  }
  return {
    average: dto.average,
    count: dto.total,
    distribution,
    categoryAverages: categoryAverages(items),
  }
}

export const reviewRepository: ReviewRepository = {
  async forProperty(propertyId, filter, signal): Promise<Page<Review> & { summary: ReviewSummary }> {
    const size = filter.limit ?? PAGE_SIZE
    // The cursor is the page number. Opaque to callers, which is the only
    // property the port requires of it.
    const page = filter.cursor ? Number(filter.cursor) : 1
    const dto = await http.get<ReviewListDto>(`/reviews/property/${propertyId}`, {
      query: { sort: filter.sort ?? 'recent', page, size },
      ...(signal ? { signal } : {}),
    })
    const items = dto.items.map(toReview)
    return {
      items,
      nextCursor: page * dto.size < dto.total ? String(page + 1) : null,
      summary: toSummary(dto, items),
    }
  },

  async mine(signal): Promise<readonly Review[]> {
    const rows = await http.get<ReviewDto[]>('/reviews/mine', signal ? { signal } : {})
    return rows.map(toReview)
  },

  async submit(draft: ReviewDraft): Promise<Review> {
    return toReview(
      await http.post<ReviewDto>('/reviews', {
        // The booking is the evidence the stay happened. The server re-checks
        // that it belongs to this guest and has completed — this field is not
        // trusted, it is just how the claim is made.
        booking_id: draft.bookingId,
        rating: draft.rating,
        title: draft.title || null,
        body: draft.body,
        categories: draft.categories,
      }),
    )
  },

  async edit(reviewId, draft): Promise<Review> {
    return toReview(
      await http.patch<ReviewDto>(`/reviews/${reviewId}`, {
        rating: draft.rating,
        title: draft.title || null,
        body: draft.body,
        categories: draft.categories,
      }),
    )
  },
}
