/** Payments, as the guest sees them. */

export type PaymentStatus =
  | 'created'
  | 'pending'
  | 'authorized'
  | 'captured'
  | 'failed'
  | 'refunded'
  | 'partially_refunded'
  | 'disputed'

export interface CheckoutSession {
  readonly paymentId: string
  readonly gatewayOrderId: string
  /** Razorpay's **public** merchant key. Authorises nothing on its own. */
  readonly keyId: string
  readonly amountMinor: number
  readonly currency: string
  readonly bookingReference: string
  readonly prefillName: string
  readonly prefillEmail: string
  readonly prefillContact: string
  readonly propertyName: string
  /** Seconds left on the booking's hold. Drives the checkout countdown. */
  readonly expiresIn: number | null
  readonly attemptNumber: number
}

export interface PaymentResult {
  readonly paymentId: string
  readonly status: string
  readonly bookingId: string
  readonly bookingReference: string
  readonly amountMinor: number
  readonly currency: string
  readonly method: string
  readonly invoiceNumber: string | null
  readonly bookingStatus: string | null
}

export interface LedgerEntry {
  readonly kind: string
  readonly amountMinor: number
  readonly currency: string
  readonly signedMinor: number
  readonly occurredAt: string
  readonly note: string | null
}

export interface PaymentRefund {
  readonly id: string
  readonly status: string
  readonly amountMinor: number
  readonly currency: string
  readonly reason: string
  readonly requestedAt: string
  readonly completedAt: string | null
}

export interface Payment {
  readonly id: string
  readonly status: PaymentStatus
  readonly bookingId: string
  readonly bookingReference: string
  readonly amountMinor: number
  readonly currency: string
  readonly method: string
  /** Card last-4 or UPI VPA. Never a card number — we are never sent one. */
  readonly instrument: string | null
  readonly createdAt: string | null
  readonly capturedAt: string | null
  readonly failureReason: string | null
  readonly refundedMinor: number
  readonly refundableMinor: number
  readonly netMinor: number
  readonly refunds: readonly PaymentRefund[]
  readonly ledger: readonly LedgerEntry[]
}

/** What the guest actually sees on their statement. */
export function methodLabel(method: string, instrument: string | null): string {
  const base =
    { upi: 'UPI', card: 'Card', netbanking: 'Net banking', wallet: 'Wallet', emi: 'EMI' }[method] ??
    'Payment'
  if (!instrument) return base
  return method === 'card' ? `${base} ···· ${instrument}` : `${base} · ${instrument}`
}

export function paymentStatusLabel(status: string): string {
  return (
    {
      created: 'Not started',
      pending: 'Processing',
      authorized: 'Authorised',
      captured: 'Paid',
      failed: 'Failed',
      refunded: 'Refunded',
      partially_refunded: 'Partly refunded',
      disputed: 'Disputed',
    }[status] ?? status
  )
}
