/** Booking queries and mutations. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRepositories } from '@/application/RepositoryContext'
import { queryKeys } from '@/application/queryKeys'
import type { CreateBookingInput } from '@/application/ports'
import type { Booking } from '@/domain/booking'

export function useBookings(filter: { status?: string; upcoming?: boolean } = {}) {
  const { bookings } = useRepositories()
  return useQuery({
    queryKey: queryKeys.bookings.list(filter),
    queryFn: ({ signal }) => bookings.list({ ...filter, limit: 20 }, signal),
  })
}

export function useBooking(identifier: string | undefined) {
  const { bookings } = useRepositories()
  return useQuery({
    queryKey: queryKeys.bookings.detail(identifier ?? ''),
    queryFn: ({ signal }) => bookings.get(identifier as string, signal),
    enabled: Boolean(identifier),
    // A booking awaiting payment carries a live countdown, and its status
    // flips the moment the payment webhook lands. Poll while that is true and
    // stop as soon as it settles — a confirmed booking never changes on its own.
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'pending_payment' ? 15_000 : false
    },
  })
}

export function useCreateBooking() {
  const { bookings } = useRepositories()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ input, idempotencyKey }: { input: CreateBookingInput; idempotencyKey: string }) =>
      bookings.create(input, idempotencyKey),
    onSuccess: (booking: Booking) => {
      queryClient.setQueryData(queryKeys.bookings.detail(booking.id), booking)
      void queryClient.invalidateQueries({ queryKey: queryKeys.bookings.all })
      // The hold has taken inventory, so anything showing availability for this
      // property is now wrong.
      void queryClient.invalidateQueries({ queryKey: queryKeys.catalog.all })
    },
    // Never automatic. A retried create is a second hold on real inventory —
    // the idempotency key makes an *intentional* retry safe, but the app should
    // not decide to retry on the guest's behalf.
    retry: false,
  })
}

export function useRefundPreview(bookingId: string | undefined, enabled = true) {
  const { bookings } = useRepositories()
  return useQuery({
    queryKey: queryKeys.bookings.refundPreview(bookingId ?? ''),
    queryFn: ({ signal }) => bookings.refundPreview(bookingId as string, signal),
    enabled: Boolean(bookingId) && enabled,
    // The refundable amount depends on how long until check-in, so it is
    // time-sensitive by construction. Never served from a warm cache.
    staleTime: 0,
  })
}

export function useCancelBooking() {
  const { bookings } = useRepositories()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ bookingId, reason }: { bookingId: string; reason?: string }) =>
      bookings.cancel(bookingId, reason),
    onSuccess: (booking) => {
      queryClient.setQueryData(queryKeys.bookings.detail(booking.id), booking)
      void queryClient.invalidateQueries({ queryKey: queryKeys.bookings.all })
      void queryClient.invalidateQueries({ queryKey: queryKeys.catalog.all })
    },
    retry: false,
  })
}

export function useInvoice(bookingId: string | undefined, enabled = true) {
  const { bookings } = useRepositories()
  return useQuery({
    queryKey: queryKeys.bookings.invoice(bookingId ?? ''),
    queryFn: ({ signal }) => bookings.invoice(bookingId as string, signal),
    enabled: Boolean(bookingId) && enabled,
    // An issued invoice is immutable — it is a legal document with a number.
    staleTime: Infinity,
  })
}
