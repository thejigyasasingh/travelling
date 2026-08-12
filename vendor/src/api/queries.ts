/**
 * Every query and mutation in the portal.
 *
 * One file, as in the admin panel: the vendor surface is small and read-mostly,
 * and twenty one-line hooks spread across ten files is harder to read than one
 * list you can scan.
 *
 * A note that applies to all of it: **nothing here sends a vendor id.** The
 * server derives it from the access token. A client-supplied id would be a
 * parameter one curl away from another host's revenue, and no amount of UI
 * makes that safe.
 */

import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/core/http'
import type {
  Arrival,
  BookingList,
  Calendar,
  Earnings,
  ListingChecklist,
  Page,
  Reports,
  Review,
  ReviewList,
  ReviewSummary,
  RoomType,
  SetAvailabilityRequest,
  SetRatesRequest,
  VendorDashboard,
  VendorProfile,
  VendorProperty,
} from './types'

export interface ListFilters {
  q?: string
  status?: string
  page?: number
  size?: number
  [key: string]: string | number | boolean | undefined
}

// ══════════════════════════════════════════════════════════════════════════
// The vendor, and the numbers
// ══════════════════════════════════════════════════════════════════════════

export const useMe = () =>
  useQuery({
    queryKey: ['vendor-me'],
    queryFn: ({ signal }) => api.get<VendorProfile>('/vendor/me', undefined, signal),
    // Status gates most of the UI, so a stale "pending" after approval would
    // keep a host locked out of a portal they can now use.
    staleTime: 30_000,
  })

export const useDashboard = () =>
  useQuery({
    queryKey: ['vendor-dashboard'],
    queryFn: ({ signal }) => api.get<VendorDashboard>('/vendor/dashboard', undefined, signal),
    refetchInterval: 60_000,
  })

export const useEarnings = (from?: string, to?: string) =>
  useQuery({
    queryKey: ['vendor-earnings', from, to],
    queryFn: ({ signal }) =>
      api.get<Earnings>('/vendor/earnings', { from_date: from, to_date: to }, signal),
  })

export const useReports = (from?: string, to?: string) =>
  useQuery({
    queryKey: ['vendor-reports', from, to],
    queryFn: ({ signal }) =>
      api.get<Reports>('/vendor/reports', { from_date: from, to_date: to }, signal),
    placeholderData: keepPreviousData,
  })

export const useArrivals = (days = 14) =>
  useQuery({
    queryKey: ['vendor-arrivals', days],
    queryFn: ({ signal }) => api.get<Arrival[]>('/vendor/arrivals', { days }, signal),
  })

// ══════════════════════════════════════════════════════════════════════════
// Properties
// ══════════════════════════════════════════════════════════════════════════

export const useProperties = (filters: ListFilters = {}) =>
  useQuery({
    queryKey: ['vendor-properties', filters],
    queryFn: ({ signal }) => api.get<Page<VendorProperty>>('/vendor/properties', filters, signal),
    placeholderData: keepPreviousData,
  })

export const useProperty = (propertyId: string | undefined) =>
  useQuery({
    queryKey: ['vendor-property', propertyId],
    queryFn: ({ signal }) =>
      api.get<VendorProperty>(`/vendor/properties/${propertyId!}`, undefined, signal),
    enabled: Boolean(propertyId),
  })

export const useChecklist = (propertyId: string | undefined) =>
  useQuery({
    queryKey: ['vendor-checklist', propertyId],
    queryFn: ({ signal }) =>
      api.get<ListingChecklist>(`/vendor/properties/${propertyId!}/checklist`, undefined, signal),
    enabled: Boolean(propertyId),
  })

/**
 * Invalidate everything a listing change can move.
 *
 * Publishing a property changes the dashboard tiles and the reports breakdown
 * as well as the list — and a host who publishes a listing and sees "0 live
 * listings" underneath it will publish it again.
 */
function useListingInvalidation() {
  const client = useQueryClient()
  return async (propertyId?: string) => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['vendor-properties'] }),
      client.invalidateQueries({ queryKey: ['vendor-dashboard'] }),
      client.invalidateQueries({ queryKey: ['vendor-reports'] }),
      propertyId
        ? client.invalidateQueries({ queryKey: ['vendor-property', propertyId] })
        : Promise.resolve(),
      propertyId
        ? client.invalidateQueries({ queryKey: ['vendor-checklist', propertyId] })
        : Promise.resolve(),
    ])
  }
}

export function useCreateProperty() {
  const invalidate = useListingInvalidation()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<VendorProperty>('/vendor/properties', body),
    onSuccess: (created) => invalidate(created.id),
  })
}

export function useUpdateProperty(propertyId: string) {
  const invalidate = useListingInvalidation()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.patch<VendorProperty>(`/vendor/properties/${propertyId}`, body),
    onSuccess: () => invalidate(propertyId),
  })
}

/** Send a draft for review. The server re-checks the checklist; this button
 *  only asks. */
export function useSubmitProperty(propertyId: string) {
  const invalidate = useListingInvalidation()
  return useMutation({
    mutationFn: () => api.post<VendorProperty>(`/vendor/properties/${propertyId}/submit`),
    onSuccess: () => invalidate(propertyId),
  })
}

/**
 * Take a listing off sale, or put it back.
 *
 * Unpublishing does **not** touch bookings already taken — those guests are
 * still arriving, and the arrivals list still shows them. The wording in the
 * UI says so, because "unpublish" reads like "cancel" to someone doing it for
 * the first time.
 */
export function useSetVisibility(propertyId: string) {
  const invalidate = useListingInvalidation()
  return useMutation({
    // The server takes an action, not a boolean. `{ published: true }` is
    // accepted by nothing and 422s — the shape is named here so the compiler
    // and the live-contract test both hold it in place.
    mutationFn: (published: boolean) =>
      api.post<VendorProperty>(`/vendor/properties/${propertyId}/visibility`, {
        action: published ? 'publish' : 'unpublish',
      }),
    onSuccess: () => invalidate(propertyId),
  })
}

// ══════════════════════════════════════════════════════════════════════════
// Rooms, pricing and availability
// ══════════════════════════════════════════════════════════════════════════

/**
 * Room types come nested inside the property, not from an endpoint of their
 * own. Selecting them here rather than in each screen keeps one `useProperty`
 * cache entry serving both, so editing a room does not leave the property
 * header showing a stale room count.
 */
export function useRoomTypes(propertyId: string | undefined): {
  data: RoomType[] | undefined
  isPending: boolean
} {
  const query = useProperty(propertyId)
  return { data: query.data?.room_types, isPending: query.isPending }
}

export function useCreateRoomType(propertyId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<RoomType>(`/vendor/properties/${propertyId}/room-types`, body),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['vendor-property', propertyId] })
      await client.invalidateQueries({ queryKey: ['vendor-checklist', propertyId] })
    },
  })
}

export function useUpdateRoomType(propertyId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ roomTypeId, body }: { roomTypeId: string; body: Record<string, unknown> }) =>
      api.patch<RoomType>(`/vendor/properties/${propertyId}/room-types/${roomTypeId}`, body),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['vendor-property', propertyId] })
      await client.invalidateQueries({ queryKey: ['vendor-calendar'] })
    },
  })
}

export const useCalendar = (
  propertyId: string | undefined,
  roomTypeId: string | undefined,
  from: string,
  to: string,
) =>
  useQuery({
    queryKey: ['vendor-calendar', propertyId, roomTypeId, from, to],
    queryFn: ({ signal }) =>
      api.get<Calendar>(
        `/vendor/properties/${propertyId!}/room-types/${roomTypeId!}/calendar`,
        { from_date: from, to_date: to },
        signal,
      ),
    enabled: Boolean(propertyId && roomTypeId),
    placeholderData: keepPreviousData,
  })

/**
 * Both calendar writes invalidate the same key.
 *
 * A rate change and an availability change land on the same nights, and a
 * calendar that shows the new price against the old inventory is a calendar a
 * host will act on.
 */
function useCalendarWrite<TBody>(
  propertyId: string,
  roomTypeId: string,
  path: 'rates' | 'availability',
) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: TBody) =>
      api.put<void>(
        `/vendor/properties/${propertyId}/room-types/${roomTypeId}/${path}`,
        body as unknown,
      ),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['vendor-calendar'] })
      await client.invalidateQueries({ queryKey: ['vendor-properties'] })
    },
  })
}

export const useSetRates = (propertyId: string, roomTypeId: string) =>
  useCalendarWrite<SetRatesRequest>(propertyId, roomTypeId, 'rates')

export const useSetAvailability = (propertyId: string, roomTypeId: string) =>
  useCalendarWrite<SetAvailabilityRequest>(propertyId, roomTypeId, 'availability')

// ══════════════════════════════════════════════════════════════════════════
// Bookings
// ══════════════════════════════════════════════════════════════════════════

export const useBookings = (filters: ListFilters = {}) =>
  useQuery({
    queryKey: ['vendor-bookings', filters],
    queryFn: ({ signal }) => api.get<BookingList>('/vendor/bookings', filters, signal),
    placeholderData: keepPreviousData,
  })

/**
 * Approve, reject or cancel.
 *
 * One hook for three verbs because they are one decision with three outcomes,
 * and all three move the same tiles. Cancelling a confirmed booking triggers a
 * refund on the server; the UI says so before it asks for confirmation, since
 * this is the one action here that moves money the host has already been told
 * about.
 */
export function useBookingDecision() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      bookingId,
      action,
      reason,
    }: {
      bookingId: string
      action: 'approve' | 'reject' | 'cancel'
      reason?: string
    }) =>
      api.post<void>(
        `/vendor/bookings/${bookingId}/${action}`,
        reason === undefined ? undefined : { reason },
      ),
    onSuccess: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ['vendor-bookings'] }),
        client.invalidateQueries({ queryKey: ['vendor-dashboard'] }),
        client.invalidateQueries({ queryKey: ['vendor-arrivals'] }),
        client.invalidateQueries({ queryKey: ['vendor-earnings'] }),
      ])
    },
  })
}

// ══════════════════════════════════════════════════════════════════════════
// Reviews
// ══════════════════════════════════════════════════════════════════════════

export const useReviews = (filters: ListFilters = {}) =>
  useQuery({
    queryKey: ['vendor-reviews', filters],
    queryFn: ({ signal }) => api.get<ReviewList>('/vendor/reviews', filters, signal),
    placeholderData: keepPreviousData,
  })

export const useReviewSummary = () =>
  useQuery({
    queryKey: ['vendor-review-summary'],
    queryFn: ({ signal }) => api.get<ReviewSummary>('/vendor/reviews/summary', undefined, signal),
  })

function useReviewInvalidation() {
  const client = useQueryClient()
  return async () => {
    await Promise.all([
      client.invalidateQueries({ queryKey: ['vendor-reviews'] }),
      client.invalidateQueries({ queryKey: ['vendor-review-summary'] }),
      client.invalidateQueries({ queryKey: ['vendor-dashboard'] }),
    ])
  }
}

export function useReplyToReview() {
  const invalidate = useReviewInvalidation()
  return useMutation({
    mutationFn: ({ reviewId, body }: { reviewId: string; body: string }) =>
      api.post<Review>(`/vendor/reviews/${reviewId}/reply`, { body }),
    onSuccess: invalidate,
  })
}

/**
 * Dispute a review.
 *
 * Worth knowing before wiring a button to it: flagging does not hide the review
 * and does not stop it counting towards the rating. It asks a human to look.
 * The UI says exactly that, because a host who believes flagging removes it
 * will flag everything and then complain that it does not work.
 */
export function useFlagReview() {
  const invalidate = useReviewInvalidation()
  return useMutation({
    mutationFn: ({ reviewId, reason }: { reviewId: string; reason: string }) =>
      api.post<Review>(`/vendor/reviews/${reviewId}/flag`, { reason }),
    onSuccess: invalidate,
  })
}
