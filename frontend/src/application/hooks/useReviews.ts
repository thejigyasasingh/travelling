/** Reviews, over the real `/reviews` endpoints. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRepositories } from '@/application/RepositoryContext'
import { queryKeys } from '@/application/queryKeys'
import type { ReviewDraft } from '@/domain/review'

export function usePropertyReviews(propertyId: string | undefined, sort = 'recent') {
  const { reviews } = useRepositories()
  return useQuery({
    queryKey: queryKeys.reviews.forProperty(propertyId ?? '', { sort }),
    queryFn: ({ signal }) => reviews.forProperty(propertyId as string, { sort }, signal),
    enabled: Boolean(propertyId),
  })
}

export function useMyReviews() {
  const { reviews } = useRepositories()
  return useQuery({
    queryKey: queryKeys.reviews.mine,
    queryFn: ({ signal }) => reviews.mine(signal),
  })
}

export function useSubmitReview() {
  const { reviews } = useRepositories()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (draft: ReviewDraft) => reviews.submit(draft),
    onSuccess: (review) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.reviews.mine })
      void queryClient.invalidateQueries({
        queryKey: ['reviews', 'property', review.propertyId],
      })
    },
  })
}

/**
 * Correct a review, within the window.
 *
 * There is deliberately no delete. A rating a guest can retract under pressure
 * from a host is a rating that means nothing, so the platform offers a
 * correction — for 48 hours, and only until the host has replied — and support
 * for anything beyond that. Both windows are the server's to enforce; the
 * response carries `can_edit` so the UI can hide the button rather than offer
 * one that 409s.
 */
export function useEditReview() {
  const { reviews } = useRepositories()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ reviewId, draft }: { reviewId: string; draft: ReviewDraft }) =>
      reviews.edit(reviewId, draft),
    onSuccess: (review) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.reviews.mine })
      void queryClient.invalidateQueries({
        queryKey: ['reviews', 'property', review.propertyId],
      })
    },
  })
}
