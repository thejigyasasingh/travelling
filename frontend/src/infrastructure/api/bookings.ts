/** `BookingRepository` over `/bookings`. */

import type { BookingRepository, CreateBookingInput, Page } from '@/application/ports'
import type { Booking } from '@/domain/booking'
import { http } from '@/infrastructure/http/client'
import type * as dto from './dto'
import { toBooking, toInvoice, toRefundPreview } from './mappers'

export const bookingRepository: BookingRepository = {
  async create(input: CreateBookingInput, idempotencyKey: string): Promise<Booking> {
    return toBooking(
      await http.post<dto.BookingDto>(
        '/bookings',
        {
          property_id: input.propertyId,
          room_type_id: input.roomTypeId,
          check_in: input.checkIn,
          check_out: input.checkOut,
          adults: input.adults,
          children: input.children,
          infants: input.infants,
          rooms: input.rooms,
          guest_name: input.guestName,
          guest_email: input.guestEmail,
          guest_phone: input.guestPhone,
          special_requests: input.specialRequests ?? null,
          // Sent so the server can reject a stale price instead of charging a
          // different amount from the one the guest agreed to.
          quoted_total_minor: input.quotedTotalMinor,
          source: 'web',
        },
        { idempotencyKey },
      ),
    )
  },

  async get(identifier, signal) {
    return toBooking(
      await http.get<dto.BookingDto>(`/bookings/${encodeURIComponent(identifier)}`, { signal }),
    )
  },

  async list(filter, signal): Promise<Page<Booking>> {
    const data = await http.get<dto.BookingListDto>('/bookings', {
      query: {
        status: filter.status,
        upcoming: filter.upcoming,
        limit: filter.limit,
        cursor: filter.cursor,
      },
      signal,
    })
    return {
      items: data.items.map(toBooking),
      nextCursor: data.next_cursor ?? null,
      totalEstimate: data.total ?? null,
    }
  },

  async refundPreview(bookingId, signal) {
    return toRefundPreview(
      await http.get<dto.RefundPreviewDto>(
        `/bookings/${encodeURIComponent(bookingId)}/refund-preview`,
        { signal },
      ),
    )
  },

  async cancel(bookingId, reason) {
    return toBooking(
      await http.post<dto.BookingDto>(`/bookings/${encodeURIComponent(bookingId)}/cancel`, {
        reason: reason ?? null,
      }),
    )
  },

  async invoice(bookingId, signal) {
    return toInvoice(
      await http.get<dto.InvoiceDto>(`/bookings/${encodeURIComponent(bookingId)}/invoice`, {
        signal,
      }),
    )
  },
}
