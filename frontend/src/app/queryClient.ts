/**
 * React Query defaults.
 *
 * The important one is `retry`: a 4xx is never retried. Retrying a 409 "those
 * dates are gone" three times shows the guest a spinner for two seconds and
 * then the same message — and retrying a 401 races the refresh interceptor.
 */

import { QueryClient } from '@tanstack/react-query'
import { ApiError, NetworkError } from '@/core/errors'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: (failureCount, error) => {
          if (error instanceof NetworkError) return failureCount < 2
          if (error instanceof ApiError) return error.isTransient && failureCount < 2
          return false
        },
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8_000),
        // Refetching every time the user alt-tabs is a lot of requests for
        // data that rarely changes that fast. Availability opts in separately.
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
      },
      mutations: {
        // A mutation is a side effect. Retrying one automatically is how a
        // guest ends up with two bookings.
        retry: false,
      },
    },
  })
}
