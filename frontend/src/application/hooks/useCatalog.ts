/** Search and property queries. */

import {
  keepPreviousData,
  useInfiniteQuery,
  useQuery,
  type UseQueryResult,
} from '@tanstack/react-query'
import { useRepositories } from '@/application/RepositoryContext'
import { queryKeys } from '@/application/queryKeys'
import type { SearchCriteria, SearchPage } from '@/application/ports'
import type { Amenity, Property, Quote } from '@/domain/property'
import type { IsoDate } from '@/core/dates'

export function useSearch(criteria: SearchCriteria, enabled = true) {
  const { catalog } = useRepositories()
  return useInfiniteQuery({
    queryKey: queryKeys.catalog.search(criteria),
    queryFn: ({ pageParam, signal }) =>
      catalog.search({ ...criteria, ...(pageParam ? { cursor: pageParam } : {}) }, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last: SearchPage) => last.nextCursor ?? undefined,
    // Keep the previous results on screen while a filter change loads. The
    // alternative is a full-page skeleton on every checkbox, which reads as the
    // app being slow even when it is fast.
    placeholderData: keepPreviousData,
    enabled,
  })
}

export function useSuggestions(query: string) {
  const { catalog } = useRepositories()
  return useQuery({
    queryKey: queryKeys.catalog.suggest(query),
    queryFn: ({ signal }) => catalog.suggest(query, signal),
    // Two characters is where suggestions start being useful rather than
    // returning half the catalogue.
    enabled: query.trim().length >= 2,
    staleTime: 5 * 60_000,
  })
}

export function useProperty(identifier: string | undefined): UseQueryResult<Property> {
  const { catalog } = useRepositories()
  return useQuery({
    queryKey: queryKeys.catalog.property(identifier ?? ''),
    queryFn: ({ signal }) => catalog.property(identifier as string, signal),
    enabled: Boolean(identifier),
    staleTime: 5 * 60_000,
  })
}

export function useAvailability(
  propertyId: string | undefined,
  from: IsoDate | undefined,
  to: IsoDate | undefined,
) {
  const { catalog } = useRepositories()
  return useQuery({
    queryKey: queryKeys.catalog.availability(propertyId ?? '', from ?? '', to ?? ''),
    queryFn: ({ signal }) =>
      catalog.availability(propertyId as string, { from: from as IsoDate, to: to as IsoDate }, signal),
    enabled: Boolean(propertyId && from && to),
    // Availability goes stale the moment someone else books. Short, not zero:
    // re-fetching on every calendar hover would hammer the API for no gain.
    staleTime: 60_000,
  })
}

export interface QuoteInput {
  readonly roomTypeId: string
  readonly checkIn: IsoDate
  readonly checkOut: IsoDate
  readonly adults: number
  readonly children: number
  readonly infants: number
  readonly rooms: number
}

export function useQuote(
  propertyId: string | undefined,
  input: Partial<QuoteInput>,
): UseQueryResult<Quote> {
  const { catalog } = useRepositories()
  const ready = Boolean(
    propertyId && input.roomTypeId && input.checkIn && input.checkOut && input.adults,
  )
  return useQuery({
    queryKey: queryKeys.catalog.quote(propertyId ?? '', input),
    queryFn: ({ signal }) => catalog.quote(propertyId as string, input as QuoteInput, signal),
    enabled: ready,
    // The quote is the number the guest agrees to pay and the server re-checks
    // it at booking time. A stale one produces a 409 at the worst moment.
    staleTime: 30_000,
    retry: 1,
  })
}

export function useAmenities(): UseQueryResult<readonly Amenity[]> {
  const { catalog } = useRepositories()
  return useQuery({
    queryKey: queryKeys.catalog.amenities,
    queryFn: ({ signal }) => catalog.amenities(signal),
    // A reference list. Refetching it is pure waste.
    staleTime: 24 * 60 * 60_000,
    gcTime: 24 * 60 * 60_000,
  })
}
