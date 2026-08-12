/**
 * The Razorpay Checkout script.
 *
 * Loaded on demand, not in `index.html`: it is a third-party script that every
 * visitor would otherwise download to browse a search page they may never buy
 * from. It is fetched when a guest reaches checkout and cached by the browser
 * after that.
 *
 * The handler receives an `order_id`, a `payment_id` and a **signature**. None
 * of it is trusted here — the three are posted to our server, which verifies the
 * HMAC against a secret the browser never sees. A client that simply *claimed*
 * payment would otherwise get a free booking.
 */

import { config } from '@/core/config'

export interface RazorpaySuccess {
  razorpay_order_id: string
  razorpay_payment_id: string
  razorpay_signature: string
}

export interface RazorpayFailure {
  error: {
    code: string
    description: string
    reason?: string
    metadata?: { order_id?: string; payment_id?: string }
  }
}

interface RazorpayOptions {
  key: string
  amount: number
  currency: string
  name: string
  description: string
  order_id: string
  prefill: { name: string; email: string; contact: string }
  notes?: Record<string, string>
  theme?: { color: string }
  handler: (response: RazorpaySuccess) => void
  modal?: { ondismiss?: () => void; confirm_close?: boolean }
}

interface RazorpayInstance {
  open: () => void
  on: (event: 'payment.failed', handler: (response: RazorpayFailure) => void) => void
}

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => RazorpayInstance
  }
}

let loader: Promise<void> | null = null

export function loadRazorpay(): Promise<void> {
  if (window.Razorpay) return Promise.resolve()

  // Single-flight: React 19 StrictMode mounts effects twice in development,
  // and two <script> tags for the same SDK is a race waiting to happen.
  loader ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = config.razorpayCheckoutUrl
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => {
      loader = null // let a retry try again
      reject(new Error('Could not load the payment window. Check your connection.'))
    }
    document.head.appendChild(script)
  })
  return loader
}

export interface OpenCheckoutArgs {
  keyId: string
  orderId: string
  amountMinor: number
  currency: string
  propertyName: string
  bookingReference: string
  prefill: { name: string; email: string; contact: string }
  onSuccess: (response: RazorpaySuccess) => void
  onFailure: (error: RazorpayFailure['error']) => void
  onDismiss: () => void
}

export async function openCheckout(args: OpenCheckoutArgs): Promise<void> {
  await loadRazorpay()
  if (!window.Razorpay) throw new Error('The payment window is unavailable.')

  const instance = new window.Razorpay({
    key: args.keyId,
    // Razorpay speaks minor units too, so this passes straight through with no
    // conversion — and therefore no rounding.
    amount: args.amountMinor,
    currency: args.currency,
    name: 'Roaming & Wandering',
    description: args.propertyName,
    order_id: args.orderId,
    prefill: args.prefill,
    notes: { booking_reference: args.bookingReference },
    theme: { color: '#0f766e' },
    handler: args.onSuccess,
    modal: {
      ondismiss: args.onDismiss,
      // Guards against closing the sheet mid-payment, which leaves a payment
      // in flight that the guest thinks they cancelled.
      confirm_close: true,
    },
  })

  instance.on('payment.failed', (response) => args.onFailure(response.error))
  instance.open()
}
