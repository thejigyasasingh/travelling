/** `PaymentRepository` over `/payments`. */

import type { Page, PaymentRepository } from '@/application/ports'
import type { Payment } from '@/domain/payment'
import { http } from '@/infrastructure/http/client'
import type * as dto from './dto'
import { toCheckoutSession, toPayment, toPaymentResult } from './mappers'

export const paymentRepository: PaymentRepository = {
  async createOrder(bookingId) {
    return toCheckoutSession(
      await http.post<dto.CheckoutSessionDto>('/payments/orders', { booking_id: bookingId }),
    )
  },

  async verify(input) {
    return toPaymentResult(
      await http.post<dto.PaymentResultDto>('/payments/verify', {
        razorpay_order_id: input.razorpayOrderId,
        razorpay_payment_id: input.razorpayPaymentId,
        razorpay_signature: input.razorpaySignature,
      }),
    )
  },

  async retry(bookingId) {
    return toPaymentResult(
      await http.post<dto.PaymentResultDto>('/payments/retry', { booking_id: bookingId }),
    )
  },

  async list(filter, signal): Promise<Page<Payment>> {
    const data = await http.get<dto.PaymentListDto>('/payments', {
      query: { limit: filter.limit, cursor: filter.cursor },
      signal,
    })
    return { items: data.items.map(toPayment), nextCursor: data.next_cursor ?? null }
  },

  async get(paymentId, signal) {
    return toPayment(
      await http.get<dto.PaymentDto>(`/payments/${encodeURIComponent(paymentId)}`, { signal }),
    )
  },
}
