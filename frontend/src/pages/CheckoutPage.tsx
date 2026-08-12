import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useBooking } from '@/application/hooks/useBookings'
import { useCreateOrder, useVerifyPayment } from '@/application/hooks/usePayments'
import { openCheckout, type RazorpayFailure } from '@/features/checkout/razorpay'
import { HoldCountdown } from '@/features/checkout/HoldCountdown'
import { formatMinor } from '@/core/money'
import { formatStay } from '@/core/dates'
import { ErrorCode, hasErrorCode, messageFor } from '@/core/errors'
import { cancellationPolicy } from '@/domain/policies'
import { isPayable } from '@/domain/booking'
import { Button } from '@/ui/Button'
import { ErrorState, LoadingBlock } from '@/ui/feedback'

type Stage = 'idle' | 'opening' | 'paying' | 'verifying' | 'done' | 'failed'

/**
 * Checkout.
 *
 * The flow is: create an order → open Razorpay → post the signed result back for
 * verification. Three properties of it are worth stating, because each one is a
 * decision that could plausibly have gone the other way.
 *
 * **The client never decides that a payment succeeded.** The Razorpay handler
 * hands us a signature, and only the server — which holds the secret — can say
 * whether it is genuine. Until it does, the UI says "confirming", not "paid".
 *
 * **A verification failure is not a payment failure.** If the money moved and
 * this request failed, the webhook still confirms the booking server-side. So
 * the guest is sent to their booking, which polls, rather than being told
 * something went wrong and invited to pay a second time.
 *
 * **A dismissed sheet is not an error.** People close the payment window to
 * check a card, and the hold is still alive. That is a returnable state, not a
 * red banner.
 */
export default function CheckoutPage() {
  const { bookingId } = useParams<{ bookingId: string }>()
  const navigate = useNavigate()

  const bookingQuery = useBooking(bookingId)
  const createOrder = useCreateOrder()
  const verify = useVerifyPayment()

  const [stage, setStage] = useState<Stage>('idle')
  const [gatewayError, setGatewayError] = useState<string | null>(null)

  const booking = bookingQuery.data

  // A booking that is already paid must never show a pay button. This covers
  // the back-button case and the case where the webhook confirmed it while the
  // guest sat on this page.
  useEffect(() => {
    if (booking && !isPayable(booking) && stage !== 'verifying') {
      if (booking.status === 'confirmed' || booking.status === 'pending_approval') {
        void navigate(`/bookings/${booking.id}/confirmed`, { replace: true })
      }
    }
  }, [booking, navigate, stage])

  if (bookingQuery.isPending) return <LoadingBlock label="Loading your booking" />
  if (bookingQuery.isError || !booking) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <ErrorState error={bookingQuery.error} />
      </div>
    )
  }

  const expired = booking.status === 'expired' || (booking.holdExpiresIn ?? 1) <= 0
  const policy = cancellationPolicy(booking.cancellationPolicy)

  async function pay() {
    if (!booking) return
    setGatewayError(null)
    setStage('opening')

    try {
      const session = await createOrder.mutateAsync(booking.id)
      setStage('paying')

      await openCheckout({
        keyId: session.keyId,
        orderId: session.gatewayOrderId,
        amountMinor: session.amountMinor,
        currency: session.currency,
        propertyName: session.propertyName,
        bookingReference: session.bookingReference,
        prefill: {
          name: session.prefillName,
          email: session.prefillEmail,
          contact: session.prefillContact,
        },
        onSuccess: (response) => {
          setStage('verifying')
          verify.mutate(
            {
              razorpayOrderId: response.razorpay_order_id,
              razorpayPaymentId: response.razorpay_payment_id,
              razorpaySignature: response.razorpay_signature,
            },
            {
              onSuccess: () => {
                setStage('done')
                void navigate(`/bookings/${booking.id}/confirmed`, { replace: true })
              },
              onError: () => {
                // The money may well have moved. The webhook is authoritative
                // and will confirm the booking, so send the guest to the page
                // that polls for it rather than inviting a second payment.
                setStage('done')
                void navigate(`/bookings/${booking.id}/confirmed`, { replace: true })
              },
            },
          )
        },
        onFailure: (error: RazorpayFailure['error']) => {
          setStage('failed')
          setGatewayError(error.description || 'The payment was declined.')
        },
        onDismiss: () => {
          // Not an error. The hold is still running and they can try again.
          setStage('idle')
        },
      })
    } catch (error) {
      setStage('failed')
      setGatewayError(messageFor(error))
    }
  }

  const paymentsDisabled = hasErrorCode(createOrder.error, ErrorCode.PAYMENTS_DISABLED)
  const busy = stage === 'opening' || stage === 'paying' || stage === 'verifying'

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <h1 className="text-2xl font-bold tracking-tight text-ink-900">Confirm and pay</h1>
      <p className="mt-1 text-sm text-ink-500">Booking {booking.reference}</p>

      {!expired && booking.holdExpiresIn !== null && (
        <div className="mt-4">
          <HoldCountdown
            seconds={booking.holdExpiresIn}
            onExpire={() => void bookingQuery.refetch()}
          />
        </div>
      )}

      {expired && (
        <div role="alert" className="mt-4 rounded-xl bg-danger-50 p-4">
          <p className="font-medium text-danger-700">This hold has expired</p>
          <p className="mt-1 text-sm text-ink-600">
            The rooms were released back to the calendar. Nothing was charged. You can start again
            — the dates may still be free.
          </p>
          <Button
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() => navigate(`/stays/${booking.propertyId}`)}
          >
            Check these dates again
          </Button>
        </div>
      )}

      <section className="mt-6 rounded-2xl border border-ink-100 p-5">
        <h2 className="font-semibold text-ink-900">{booking.propertyName}</h2>
        <p className="mt-0.5 text-sm text-ink-500">{booking.roomTypeName}</p>
        <dl className="mt-4 space-y-2 text-sm">
          <div className="flex justify-between">
            <dt className="text-ink-500">Dates</dt>
            <dd className="font-medium text-ink-800">
              {formatStay(booking.checkIn, booking.checkOut)} · {booking.nights} night
              {booking.nights === 1 ? '' : 's'}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-ink-500">Guests</dt>
            <dd className="font-medium text-ink-800">
              {booking.adults + booking.children} in {booking.rooms} room
              {booking.rooms === 1 ? '' : 's'}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-ink-500">Lead guest</dt>
            <dd className="font-medium text-ink-800">{booking.guestName}</dd>
          </div>
        </dl>
      </section>

      <section className="mt-5 rounded-2xl border border-ink-100 p-5">
        <h2 className="font-semibold text-ink-900">Price</h2>
        <dl className="mt-3 space-y-1.5 text-sm">
          <Row label="Accommodation" value={formatMinor(booking.accommodationMinor, booking.currency)} />
          {booking.extraGuestMinor > 0 && (
            <Row label="Extra guests" value={formatMinor(booking.extraGuestMinor, booking.currency)} />
          )}
          {booking.cleaningFeeMinor > 0 && (
            <Row label="Cleaning fee" value={formatMinor(booking.cleaningFeeMinor, booking.currency)} />
          )}
          <Row label="Taxes" value={formatMinor(booking.taxMinor, booking.currency)} />
          <div className="flex justify-between border-t border-ink-100 pt-2 text-base font-semibold text-ink-900">
            <dt>Total</dt>
            <dd className="tabular-nums">{formatMinor(booking.totalMinor, booking.currency)}</dd>
          </div>
        </dl>
        <p className="mt-2 text-xs text-ink-500">
          Charged once, in {booking.currency}. {policy.short}.
        </p>
      </section>

      {(gatewayError || createOrder.isError) && (
        <div role="alert" className="mt-5 rounded-xl bg-danger-50 p-4">
          <p className="font-medium text-danger-700">
            {paymentsDisabled ? 'Payments are unavailable right now' : 'That payment did not go through'}
          </p>
          <p className="mt-1 text-sm text-ink-600">
            {paymentsDisabled
              ? 'We cannot take payments at the moment. Your rooms are still held — please try again shortly.'
              : (gatewayError ?? messageFor(createOrder.error))}
          </p>
          <p className="mt-1 text-sm text-ink-600">
            Nothing has been charged. Your booking is still held.
          </p>
        </div>
      )}

      <div className="mt-6">
        <Button size="lg" fullWidth loading={busy} disabled={expired} onClick={() => void pay()}>
          {stage === 'verifying'
            ? 'Confirming your payment…'
            : `Pay ${formatMinor(booking.totalMinor, booking.currency)}`}
        </Button>
        <p className="mt-3 text-center text-xs text-ink-500">
          Payments are processed by Razorpay. Card details are entered in their window and never
          reach our servers.
        </p>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-ink-600">
      <dt>{label}</dt>
      <dd className="tabular-nums">{value}</dd>
    </div>
  )
}
