/** Payment queries and mutations. */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRepositories } from '@/application/RepositoryContext'
import { queryKeys } from '@/application/queryKeys'

export function usePayments() {
  const { payments } = useRepositories()
  return useQuery({
    queryKey: queryKeys.payments.list({ limit: 20 }),
    queryFn: ({ signal }) => payments.list({ limit: 20 }, signal),
  })
}

export function usePayment(paymentId: string | undefined) {
  const { payments } = useRepositories()
  return useQuery({
    queryKey: queryKeys.payments.detail(paymentId ?? ''),
    queryFn: ({ signal }) => payments.get(paymentId as string, signal),
    enabled: Boolean(paymentId),
  })
}

export function useCreateOrder() {
  const { payments } = useRepositories()
  return useMutation({
    mutationFn: (bookingId: string) => payments.createOrder(bookingId),
    // Safe to call twice — the server returns the same order rather than
    // creating a second — but an automatic retry on a slow network would open
    // a second checkout sheet, so retries stay a user decision.
    retry: false,
  })
}

export function useVerifyPayment() {
  const { payments } = useRepositories()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (input: {
      razorpayOrderId: string
      razorpayPaymentId: string
      razorpaySignature: string
    }) => payments.verify(input),
    onSuccess: () => {
      // The booking is confirmed and an invoice exists. Everything about it on
      // screen is now stale.
      void queryClient.invalidateQueries({ queryKey: queryKeys.bookings.all })
      void queryClient.invalidateQueries({ queryKey: queryKeys.payments.all })
    },
    // Money has already moved by the time this runs; the webhook confirms the
    // booking regardless. One attempt, then show the guest a status page.
    retry: 1,
  })
}
