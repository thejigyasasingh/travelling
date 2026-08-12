/**
 * Every admin query and mutation.
 *
 * One file because the admin surface is small, flat and read-mostly; splitting
 * it per feature would spread twenty one-line functions across ten files.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  keepPreviousData,
} from '@tanstack/react-query'
import { api } from '@/core/http'
import type {
  AdminBooking,
  AdminPayment,
  AdminProperty,
  AdminUser,
  AdminVendor,
  Analytics,
  Coupon,
  CouponPage,
  CouponUsage,
  CurrentUser,
  Dashboard,
  NotificationRow,
  Paged,
  Ticket,
  TicketPage,
  VendorDetail,
} from './types'

export interface ListFilters {
  q?: string
  status?: string
  page?: number
  size?: number
  [key: string]: string | number | boolean | undefined
}

/** Every list shares this shape, so paging and filtering behave identically
 *  across ten tables rather than being re-invented per screen. */
function listQuery<T>(key: string, path: string, filters: ListFilters) {
  return {
    queryKey: [key, filters] as const,
    queryFn: ({ signal }: { signal: AbortSignal }) =>
      api.get<Paged<T>>(path, filters, signal),
    // Keeps the current page visible while the next loads. A table that blanks
    // on every page change reads as broken.
    placeholderData: keepPreviousData,
  }
}

export const useDashboard = (windowDays = 30) =>
  useQuery({
    queryKey: ['dashboard', windowDays],
    queryFn: ({ signal }) =>
      api.get<Dashboard>('/admin/dashboard', { window_days: windowDays }, signal),
    // The action queue is the one part an admin acts on, so it should not be
    // stale by more than a minute.
    staleTime: 60_000,
  })

export const useAnalytics = (from?: string, to?: string) =>
  useQuery({
    queryKey: ['analytics', from, to],
    queryFn: ({ signal }) =>
      api.get<Analytics>('/admin/analytics', { from_date: from, to_date: to }, signal),
  })

export const useUsers = (filters: ListFilters) =>
  useQuery(listQuery<AdminUser>('users', '/admin/users', filters))

export const useProperties = (filters: ListFilters) =>
  useQuery(listQuery<AdminProperty>('properties', '/admin/properties', filters))

export const useBookings = (filters: ListFilters) =>
  useQuery(listQuery<AdminBooking>('bookings', '/admin/bookings', filters))

export const usePayments = (filters: ListFilters) =>
  useQuery(listQuery<AdminPayment>('payments', '/admin/payments', filters))

export const useVendors = (filters: ListFilters) =>
  useQuery(listQuery<AdminVendor>('vendors', '/admin/vendors', filters))

export const useNotifications = (filters: ListFilters) =>
  useQuery(listQuery<NotificationRow>('notifications', '/admin/notifications', filters))

export const useVendor = (vendorId: string | undefined) =>
  useQuery({
    queryKey: ['vendor', vendorId],
    queryFn: ({ signal }) => api.get<VendorDetail>(`/admin/vendors/${vendorId}`, {}, signal),
    enabled: Boolean(vendorId),
  })

export const useCoupons = (filters: ListFilters) =>
  useQuery({
    queryKey: ['coupons', filters] as const,
    queryFn: ({ signal }) => api.get<CouponPage>('/admin/coupons', filters, signal),
    placeholderData: keepPreviousData,
  })

export const useCouponUsage = (couponId: string | undefined) =>
  useQuery({
    queryKey: ['coupon-usage', couponId],
    queryFn: ({ signal }) =>
      api.get<CouponUsage>(`/admin/coupons/${couponId}/usage`, {}, signal),
    enabled: Boolean(couponId),
  })

export const useTickets = (filters: ListFilters) =>
  useQuery({
    queryKey: ['tickets', filters] as const,
    queryFn: ({ signal }) => api.get<TicketPage>('/admin/tickets', filters, signal),
    placeholderData: keepPreviousData,
    // A support queue that is a minute stale is a ticket answered a minute
    // late, so this refetches while the tab is open.
    refetchInterval: 60_000,
  })

export const useTicketCounts = () =>
  useQuery({
    queryKey: ['ticket-counts'],
    queryFn: ({ signal }) =>
      api.get<{ counts: Record<string, number> }>('/admin/tickets/counts', {}, signal),
  })

export const useMe = () =>
  useQuery({
    queryKey: ['me'],
    queryFn: ({ signal }) => api.get<CurrentUser>('/auth/me', {}, signal),
    retry: false,
  })

// ── mutations ─────────────────────────────────────────────────────────────

/** Invalidating both the list and the dashboard: a vendor approval changes the
 *  action-queue tile, and an admin who approves five vendors and still sees
 *  "5 pending" stops trusting the number. */
function useAdminMutation<TArgs, TResult>(
  mutationFn: (args: TArgs) => Promise<TResult>,
  invalidate: string[],
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      for (const key of [...invalidate, 'dashboard']) {
        void queryClient.invalidateQueries({ queryKey: [key] })
      }
    },
  })
}

export const useApproveVendor = () =>
  useAdminMutation(
    ({ id, commissionBps }: { id: string; commissionBps?: number }) =>
      api.post<VendorDetail>(`/admin/vendors/${id}/approve`, {
        commission_bps: commissionBps ?? null,
      }),
    ['vendors', 'vendor'],
  )

export const useRejectVendor = () =>
  useAdminMutation(
    ({ id, reason }: { id: string; reason: string }) =>
      api.post<VendorDetail>(`/admin/vendors/${id}/reject`, { reason }),
    ['vendors', 'vendor'],
  )

export const useSuspendVendor = () =>
  useAdminMutation(
    ({ id, reason }: { id: string; reason: string }) =>
      api.post<VendorDetail>(`/admin/vendors/${id}/suspend`, { reason }),
    ['vendors', 'vendor'],
  )

export const useBeginVendorReview = () =>
  useAdminMutation(
    ({ id }: { id: string }) => api.post<VendorDetail>(`/admin/vendors/${id}/review`),
    ['vendors', 'vendor'],
  )

export const useReviewProperty = () =>
  useAdminMutation(
    ({ id, approve, reason }: { id: string; approve: boolean; reason?: string }) =>
      api.post<unknown>(`/admin/properties/${id}/review`, {
        approve,
        reason: reason ?? null,
      }),
    ['properties'],
  )

export const useSuspendProperty = () =>
  useAdminMutation(
    ({ id, reason }: { id: string; reason: string }) =>
      api.post<unknown>(`/admin/properties/${id}/suspend`, { reason }),
    ['properties'],
  )

export const useCreateCoupon = () =>
  useAdminMutation(
    (body: Record<string, unknown>) => api.post<Coupon>('/admin/coupons', body),
    ['coupons'],
  )

export const useSetCouponStatus = () =>
  useAdminMutation(
    ({ id, active }: { id: string; active: boolean }) =>
      api.patch<Coupon>(`/admin/coupons/${id}/status`, { active }),
    ['coupons'],
  )

export const useResolveTicket = () =>
  useAdminMutation(
    ({ id, resolution }: { id: string; resolution: string }) =>
      api.post<Ticket>(`/admin/tickets/${id}/resolve`, { resolution }),
    ['tickets', 'ticket-counts'],
  )

export const useReplyToTicket = () =>
  useAdminMutation(
    ({ id, body, internal }: { id: string; body: string; internal: boolean }) =>
      api.post<Ticket>(`/support/tickets/${id}/reply`, { body, internal }),
    ['tickets'],
  )

export const useSetTicketPriority = () =>
  useAdminMutation(
    ({ id, priority }: { id: string; priority: string }) =>
      api.patch<Ticket>(`/admin/tickets/${id}/priority`, { priority }),
    ['tickets'],
  )

export const useRefundPayment = () =>
  useAdminMutation(
    ({ id, amountMinor, reason }: { id: string; amountMinor?: number; reason: string }) =>
      api.post<unknown>(`/admin/payments/${id}/refund`, {
        amount_minor: amountMinor ?? null,
        reason,
      }),
    ['payments'],
  )
