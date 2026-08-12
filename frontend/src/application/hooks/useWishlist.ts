/** The wishlist, with optimistic writes — a heart must turn red instantly. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRepositories } from '@/application/RepositoryContext'
import { queryKeys } from '@/application/queryKeys'
import type { WishlistEntry } from '@/domain/wishlist'
import { sortByRecent } from '@/domain/wishlist'

export function useWishlist() {
  const { wishlist } = useRepositories()
  return useQuery({
    queryKey: queryKeys.wishlist.all,
    queryFn: async () => sortByRecent(await wishlist.list()),
    staleTime: 60_000,
  })
}

export function useToggleWishlist() {
  const { wishlist } = useRepositories()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ entry, saved }: { entry: WishlistEntry; saved: boolean }) => {
      if (saved) await wishlist.remove(entry.propertyId)
      else await wishlist.add(entry)
    },
    // Optimistic: a heart that waits for a round trip feels broken, and this
    // one is not even a round trip today.
    onMutate: async ({ entry, saved }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.wishlist.all })
      const previous = queryClient.getQueryData<WishlistEntry[]>(queryKeys.wishlist.all) ?? []
      queryClient.setQueryData<WishlistEntry[]>(
        queryKeys.wishlist.all,
        saved
          ? previous.filter((e) => e.propertyId !== entry.propertyId)
          : [entry, ...previous.filter((e) => e.propertyId !== entry.propertyId)],
      )
      return { previous }
    },
    onError: (_error, _variables, context) => {
      // Roll back to exactly what was there, not to a re-derived guess.
      if (context?.previous) queryClient.setQueryData(queryKeys.wishlist.all, context.previous)
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.wishlist.all })
    },
  })
}

export function useClearWishlist() {
  const { wishlist } = useRepositories()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => wishlist.clear(),
    onSuccess: () => queryClient.setQueryData(queryKeys.wishlist.all, []),
  })
}
