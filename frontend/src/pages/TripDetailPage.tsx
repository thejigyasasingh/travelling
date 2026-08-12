import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useBooking, useCancelBooking, useInvoice, useRefundPreview } from '@/application/hooks/useBookings'
import { formatMinor } from '@/core/money'
import { formatDateTime, formatStay } from '@/core/dates'
import { messageFor } from '@/core/errors'
import { canRequestCancellation, canReview, guestSummary, statusPresentation } from '@/domain/booking'
import { cancellationPolicy, REFUND_FOOTNOTE } from '@/domain/policies'
import { Button, ButtonLink } from '@/ui/Button'
import { Badge, ErrorState, LoadingBlock, Skeleton } from '@/ui/feedback'
import { Modal } from '@/ui/Modal'

/**
 * One trip, with everything a guest needs after booking: the details, the
 * invoice, and cancellation.
 *
 * Cancellation shows the **server's** refund preview before asking for
 * confirmation, itemised. Guessing the refund client-side and being wrong is a
 * dispute; showing a number the guest agreed to before pressing the button is
 * how the conversation is avoided entirely.
 */
export default function TripDetailPage() {
  const { bookingId } = useParams<{ bookingId: string }>()
  const { data: booking, isPending, isError, error, refetch } = useBooking(bookingId)

  const [cancelOpen, setCancelOpen] = useState(false)
  const [invoiceOpen, setInvoiceOpen] = useState(false)
  const [reason, setReason] = useState('')

  const refund = useRefundPreview(bookingId, cancelOpen)
  const cancel = useCancelBooking()
  const invoice = useInvoice(bookingId, invoiceOpen)

  if (isPending) return <LoadingBlock label="Loading your trip" />
  if (isError || !booking) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <ErrorState error={error} onRetry={() => void refetch()} />
      </div>
    )
  }

  const status = statusPresentation(booking.status)
  const policy = cancellationPolicy(booking.cancellationPolicy)

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <nav aria-label="Breadcrumb" className="mb-4 text-sm text-ink-500 no-print">
        <Link to="/trips" className="hover:text-brand-600">
          My trips
        </Link>
        <span className="mx-1.5">/</span>
        <span className="text-ink-700">{booking.reference}</span>
      </nav>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink-900">{booking.propertyName}</h1>
          <p className="mt-1 text-sm text-ink-500">
            {formatStay(booking.checkIn, booking.checkOut)} · {booking.nights} night
            {booking.nights === 1 ? '' : 's'}
          </p>
        </div>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>

      <p className="mt-2 text-sm text-ink-600">{status.hint}</p>

      {booking.status === 'pending_payment' && (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-warning-50 p-4 no-print">
          <p className="flex-1 text-sm text-warning-700">
            This booking is not paid for yet. Your rooms are held until the window closes.
          </p>
          <ButtonLink to={`/checkout/${booking.id}`} size="sm">
            Pay now
          </ButtonLink>
        </div>
      )}

      <section className="mt-6 rounded-2xl border border-ink-100 p-5">
        <h2 className="font-semibold text-ink-900">Your stay</h2>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          <Detail label="Reference" value={booking.reference} mono />
          <Detail label="Room" value={booking.roomTypeName} />
          <Detail label="Guests" value={guestSummary(booking)} />
          <Detail label="Lead guest" value={booking.guestName} />
          <Detail label="Contact" value={`${booking.guestEmail} · ${booking.guestPhone}`} />
          {booking.confirmedAt && (
            <Detail label="Confirmed" value={formatDateTime(booking.confirmedAt)} />
          )}
          {booking.propertyAddress && (
            <div className="sm:col-span-2">
              <Detail label="Address" value={booking.propertyAddress} />
            </div>
          )}
          {booking.specialRequests && (
            <div className="sm:col-span-2">
              <Detail label="Your requests" value={booking.specialRequests} />
            </div>
          )}
        </dl>
      </section>

      <section className="mt-5 rounded-2xl border border-ink-100 p-5">
        <h2 className="font-semibold text-ink-900">What you paid</h2>
        <dl className="mt-3 space-y-1.5 text-sm">
          <Row label="Accommodation" value={formatMinor(booking.accommodationMinor, booking.currency)} />
          {booking.extraGuestMinor > 0 && (
            <Row label="Extra guests" value={formatMinor(booking.extraGuestMinor, booking.currency)} />
          )}
          {booking.cleaningFeeMinor > 0 && (
            <Row label="Cleaning fee" value={formatMinor(booking.cleaningFeeMinor, booking.currency)} />
          )}
          <Row label="Taxes" value={formatMinor(booking.taxMinor, booking.currency)} />
          <div className="flex justify-between border-t border-ink-100 pt-2 font-semibold text-ink-900">
            <dt>Total</dt>
            <dd className="tabular-nums">{formatMinor(booking.totalMinor, booking.currency)}</dd>
          </div>
        </dl>

        {booking.nightlyRates.length > 0 && (
          <details className="mt-4">
            <summary className="cursor-pointer text-sm text-brand-600">Night-by-night rates</summary>
            <ul className="mt-2 space-y-1 text-sm text-ink-600">
              {booking.nightlyRates.map((night) => (
                <li key={night.date} className="flex justify-between">
                  <span>{night.date}</span>
                  <span className="tabular-nums">
                    {formatMinor(night.amountMinor, booking.currency)}
                  </span>
                </li>
              ))}
            </ul>
          </details>
        )}

        {booking.invoiceNumber && (
          <Button variant="secondary" size="sm" className="mt-4 no-print" onClick={() => setInvoiceOpen(true)}>
            View GST invoice
          </Button>
        )}
      </section>

      {booking.refund && (
        <section className="mt-5 rounded-2xl border border-ink-100 p-5">
          <h2 className="font-semibold text-ink-900">Refund</h2>
          <p className="mt-2 text-sm text-ink-600">
            {formatMinor(booking.refund.amountMinor, booking.refund.currency)}{' '}
            {booking.refund.status === 'completed'
              ? `was refunded on ${formatDateTime(booking.refund.completedAt)}.`
              : 'is being processed. Bank refunds usually take 5–7 working days to appear.'}
          </p>
          {booking.refund.reason && (
            <p className="mt-1 text-xs text-ink-500">Reason: {booking.refund.reason}</p>
          )}
        </section>
      )}

      <div className="mt-6 flex flex-wrap gap-3 no-print">
        {canReview(booking) && (
          <ButtonLink to={`/trips/${booking.id}/review`}>Write a review</ButtonLink>
        )}
        <ButtonLink to={`/stays/${booking.propertyId}`} variant="secondary">
          View the property
        </ButtonLink>
        {canRequestCancellation(booking) && (
          <Button variant="ghost" onClick={() => setCancelOpen(true)}>
            Cancel this booking
          </Button>
        )}
      </div>

      <p className="mt-6 text-xs text-ink-500">
        {policy.label} cancellation — {policy.detail} {REFUND_FOOTNOTE}
      </p>

      {/* ── cancellation ────────────────────────────────────────────────── */}
      <Modal
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        title="Cancel this booking?"
        description="Here is exactly what comes back to you, under the policy you booked under."
        footer={
          <>
            <Button variant="ghost" onClick={() => setCancelOpen(false)}>
              Keep my booking
            </Button>
            <Button
              variant="danger"
              loading={cancel.isPending}
              disabled={refund.data?.cancellable === false}
              onClick={() =>
                cancel.mutate(
                  { bookingId: booking.id, ...(reason ? { reason } : {}) },
                  { onSuccess: () => setCancelOpen(false) },
                )
              }
            >
              Cancel booking
            </Button>
          </>
        }
      >
        {refund.isPending ? (
          <Skeleton className="h-40" />
        ) : refund.isError ? (
          <ErrorState error={refund.error} />
        ) : refund.data ? (
          <div className="space-y-4">
            <dl className="space-y-1.5 text-sm">
              <Row label="Accommodation" value={formatMinor(refund.data.accommodationMinor, refund.data.currency)} />
              {refund.data.cleaningFeeMinor > 0 && (
                <Row label="Cleaning fee" value={formatMinor(refund.data.cleaningFeeMinor, refund.data.currency)} />
              )}
              <Row label="Taxes" value={formatMinor(refund.data.taxMinor, refund.data.currency)} />
              <div className="flex justify-between border-t border-ink-100 pt-2 text-base font-semibold text-ink-900">
                <dt>You get back</dt>
                <dd className="tabular-nums">
                  {formatMinor(refund.data.totalMinor, refund.data.currency)}
                </dd>
              </div>
            </dl>
            <p className="rounded-lg bg-ink-50 p-3 text-xs text-ink-600">
              {refund.data.reason} ({refund.data.appliedPercent} of the room rate, with{' '}
              {Math.round(refund.data.hoursBeforeCheckIn)} hours to check-in). {REFUND_FOOTNOTE}
            </p>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-ink-700">
                Why are you cancelling? <span className="text-ink-400">(optional)</span>
              </span>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                maxLength={200}
                className="w-full rounded-xl border border-ink-200 px-3 py-2 text-sm"
              />
            </label>
            {cancel.isError && (
              <p role="alert" className="text-sm text-danger-700">
                {messageFor(cancel.error)}
              </p>
            )}
          </div>
        ) : null}
      </Modal>

      {/* ── invoice ─────────────────────────────────────────────────────── */}
      <Modal
        open={invoiceOpen}
        onClose={() => setInvoiceOpen(false)}
        title="Tax invoice"
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setInvoiceOpen(false)}>
              Close
            </Button>
            <Button onClick={() => window.print()}>Print or save as PDF</Button>
          </>
        }
      >
        {invoice.isPending ? (
          <Skeleton className="h-64" />
        ) : invoice.isError ? (
          <ErrorState error={invoice.error} />
        ) : invoice.data ? (
          <div className="space-y-4 text-sm">
            <div className="flex justify-between">
              <div>
                <p className="font-semibold text-ink-900">{invoice.data.supplierName}</p>
                <p className="whitespace-pre-line text-xs text-ink-500">
                  {invoice.data.supplierAddress}
                </p>
                {invoice.data.supplierGstin && (
                  <p className="mt-1 font-mono text-xs text-ink-500">
                    GSTIN {invoice.data.supplierGstin}
                  </p>
                )}
              </div>
              <div className="text-right">
                <p className="font-mono font-semibold text-ink-900">{invoice.data.number}</p>
                <p className="text-xs text-ink-500">{formatDateTime(invoice.data.issuedAt)}</p>
                <p className="text-xs text-ink-500">FY {invoice.data.financialYear}</p>
              </div>
            </div>

            <table className="w-full border-t border-ink-100 text-left">
              <thead>
                <tr className="text-xs text-ink-500">
                  <th className="py-2 font-medium">Description</th>
                  <th className="py-2 text-right font-medium">Qty</th>
                  <th className="py-2 text-right font-medium">Rate</th>
                  <th className="py-2 text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {invoice.data.lines.map((line, index) => (
                  <tr key={index}>
                    <td className="py-2 text-ink-700">
                      {line.description}
                      {line.hsnSac && (
                        <span className="block text-xs text-ink-400">HSN {line.hsnSac}</span>
                      )}
                    </td>
                    <td className="py-2 text-right tabular-nums">{line.quantity}</td>
                    <td className="py-2 text-right tabular-nums">
                      {formatMinor(line.unitPriceMinor, invoice.data.currency)}
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      {formatMinor(line.amountMinor, invoice.data.currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <dl className="space-y-1 border-t border-ink-100 pt-3">
              <Row label="Subtotal" value={formatMinor(invoice.data.subtotalMinor, invoice.data.currency)} />
              {invoice.data.cgstMinor > 0 && (
                <Row label="CGST" value={formatMinor(invoice.data.cgstMinor, invoice.data.currency)} />
              )}
              {invoice.data.sgstMinor > 0 && (
                <Row label="SGST" value={formatMinor(invoice.data.sgstMinor, invoice.data.currency)} />
              )}
              {invoice.data.igstMinor > 0 && (
                <Row label="IGST" value={formatMinor(invoice.data.igstMinor, invoice.data.currency)} />
              )}
              <div className="flex justify-between border-t border-ink-100 pt-2 font-semibold text-ink-900">
                <dt>Total</dt>
                <dd className="tabular-nums">
                  {formatMinor(invoice.data.totalMinor, invoice.data.currency)}
                </dd>
              </div>
            </dl>
            <p className="text-xs text-ink-500">
              {invoice.data.totalInWords} · Place of supply: {invoice.data.placeOfSupply}
            </p>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs font-medium text-ink-500">{label}</dt>
      <dd className={`mt-0.5 text-sm text-ink-900 ${mono ? 'font-mono' : ''}`}>{value}</dd>
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
