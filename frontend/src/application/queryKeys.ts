/**
 * Query keys, in one place.
 *
 * Keys scattered across files drift, and a drifted key means a mutation
 * invalidates nothing — the screen keeps showing a cancelled booking as
 * confirmed. The hierarchy is deliberate: `bookings.all` invalidates every
 * booking query, `bookings.detail(id)` just the one.
 */

import type { SearchCriteria } from './ports'

export const queryKeys = {
  auth: {
    me: ['auth', 'me'] as const,
    sessions: ['auth', 'sessions'] as const,
  },
  catalog: {
    all: ['catalog'] as const,
    // The whole criteria object is the key: change a filter, get a different
    // cache entry, and going back to the previous filter is instant.
    search: (criteria: SearchCriteria) => ['catalog', 'search', criteria] as const,
    suggest: (q: string) => ['catalog', 'suggest', q] as const,
    property: (identifier: string) => ['catalog', 'property', identifier] as const,
    availability: (propertyId: string, from: string, to: string) =>
      ['catalog', 'availability', propertyId, from, to] as const,
    quote: (propertyId: string, input: unknown) => ['catalog', 'quote', propertyId, input] as const,
    amenities: ['catalog', 'amenities'] as const,
  },
  bookings: {
    all: ['bookings'] as const,
    list: (filter: unknown) => ['bookings', 'list', filter] as const,
    detail: (identifier: string) => ['bookings', 'detail', identifier] as const,
    refundPreview: (id: string) => ['bookings', 'refund-preview', id] as const,
    invoice: (id: string) => ['bookings', 'invoice', id] as const,
  },
  payments: {
    all: ['payments'] as const,
    list: (filter: unknown) => ['payments', 'list', filter] as const,
    detail: (id: string) => ['payments', 'detail', id] as const,
  },
  reviews: {
    all: ['reviews'] as const,
    forProperty: (propertyId: string, filter: unknown) =>
      ['reviews', 'property', propertyId, filter] as const,
    mine: ['reviews', 'mine'] as const,
  },
  wishlist: {
    all: ['wishlist'] as const,
  },
} as const
