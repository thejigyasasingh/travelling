/**
 * The booking widget: dates, guests, live quote, "Reserve".
 *
 * The price shown here is the **server's** quote, never a client-side
 * calculation. Nightly rates vary by date, weekends and seasons have
 * multipliers, and taxes are slabbed — reimplementing that here would produce a
 * number that disagrees with the server at checkout, which the API correctly
 * rejects with a 409. So the widget asks, waits, and shows what it is told.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuote } from '@/application/hooks/useCatalog'
import type { Property } from '@/domain/property'
import { addDays, isValidStay, nightsBetween, today, type IsoDate } from '@/core/dates'
import { formatMinor } from '@/core/money'
import { cancellationPolicy } from '@/domain/policies'
import { Button } from '@/ui/Button'
import { Spinner } from '@/ui/Button'
import { InlineError } from '@/ui/feedback'
import { cn } from '@/ui/cn'

export interface StaySelection {
  /** Empty string means "not chosen yet" — what an empty date input gives us. */
  checkIn: IsoDate
  checkOut: IsoDate
  adults: number
  children: number
  infants: number
  rooms: number
  roomTypeId: string
}

export function BookingWidget({
  property,
  initial,
}: {
  property: Property
  initial: Partial<StaySelection>
}) {
  const navigate = useNavigate()
  const firstRoom = property.roomTypes[0]

  const [selection, setSelection] = useState<StaySelection>({
    checkIn: initial.checkIn ?? '',
    checkOut: initial.checkOut ?? '',
    adults: initial.adults ?? 2,
    children: initial.children ?? 0,
    infants: initial.infants ?? 0,
    rooms: initial.rooms ?? 1,
    roomTypeId: initial.roomTypeId ?? firstRoom?.id ?? '',
  })

  // Derived, not synced. A property that loads after this mounts — or a
  // different one navigated to — would otherwise leave `roomTypeId` pointing at
  // a room that does not exist, and an effect to repair it renders once with the
  // broken value first.
  const roomTypeId =
    property.roomTypes.find((r) => r.id === selection.roomTypeId)?.id ?? firstRoom?.id ?? ''

  const stayValid = isValidStay({ checkIn: selection.checkIn, checkOut: selection.checkOut })
  const nights = stayValid ? nightsBetween(selection.checkIn, selection.checkOut) : 0
  const room = property.roomTypes.find((r) => r.id === roomTypeId)

  const quoteQuery = useQuote(property.id, {
    roomTypeId,
    ...(stayValid ? { checkIn: selection.checkIn, checkOut: selection.checkOut } : {}),
    adults: selection.adults,
    children: selection.children,
    infants: selection.infants,
    rooms: selection.rooms,
  })
  const quote = quoteQuery.data

  const belowMinNights = room !== undefined && nights > 0 && nights < room.minNights
  const canReserve = stayValid && !belowMinNights && quote?.isAvailable === true

  function reserve() {
    const params = new URLSearchParams({
      room_type: roomTypeId,
      check_in: selection.checkIn,
      check_out: selection.checkOut,
      adults: String(selection.adults),
      children: String(selection.children),
      infants: String(selection.infants),
      rooms: String(selection.rooms),
    })
    void navigate(`/book/${property.id}?${params.toString()}`)
  }

  return (
    <div className="rounded-2xl border border-ink-200 bg-white p-5 shadow-card">
      <div className="flex items-baseline justify-between">
        <div>
          {room ? (
            <>
              <span className="text-xl font-semibold text-ink-900">
                {formatMinor(room.baseRateMinor, room.currency, { compact: true })}
              </span>
              <span className="text-sm text-ink-500"> / night</span>
            </>
          ) : (
            <span className="text-sm text-ink-500">Select a room</span>
          )}
        </div>
        {property.instantBooking && (
          <span className="text-xs font-medium text-brand-700">Instant booking</span>
        )}
      </div>

      <div className="mt-4 space-y-3">
        {property.roomTypes.length > 1 && (
          <div>
            <label htmlFor="room-type" className="mb-1 block text-xs font-medium text-ink-600">
              Room
            </label>
            <select
              id="room-type"
              value={roomTypeId}
              onChange={(e) => setSelection((s) => ({ ...s, roomTypeId: e.target.value }))}
              className="h-11 w-full rounded-xl border border-ink-200 px-3 text-sm"
            >
              {property.roomTypes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} — {formatMinor(r.baseRateMinor, r.currency, { compact: true })}/night
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <DateInput
            label="Check in"
            value={selection.checkIn}
            min={today()}
            onChange={(value) =>
              setSelection((s) => ({
                ...s,
                checkIn: value,
                checkOut: s.checkOut && value >= s.checkOut ? addDays(value, 1) : s.checkOut,
              }))
            }
          />
          <DateInput
            label="Check out"
            value={selection.checkOut}
            min={selection.checkIn ? addDays(selection.checkIn, 1) : addDays(today(), 1)}
            onChange={(value) => setSelection((s) => ({ ...s, checkOut: value }))}
          />
        </div>

        <div className="grid grid-cols-3 gap-2">
          <NumberInput
            label="Adults"
            value={selection.adults}
            min={1}
            max={room?.maxAdults ?? 16}
            onChange={(v) => setSelection((s) => ({ ...s, adults: v }))}
          />
          <NumberInput
            label="Children"
            value={selection.children}
            min={0}
            max={room?.maxChildren ?? 10}
            onChange={(v) => setSelection((s) => ({ ...s, children: v }))}
          />
          <NumberInput
            label="Rooms"
            value={selection.rooms}
            min={1}
            max={room?.totalUnits ?? 8}
            onChange={(v) => setSelection((s) => ({ ...s, rooms: v }))}
          />
        </div>
      </div>

      {/* ── the quote ───────────────────────────────────────────────────── */}
      <div className="mt-4 min-h-24 border-t border-ink-100 pt-4">
        {!stayValid ? (
          <p className="text-sm text-ink-500">Choose your dates to see the total.</p>
        ) : belowMinNights ? (
          <p className="text-sm text-warning-700">
            This room has a {room?.minNights}-night minimum stay.
          </p>
        ) : quoteQuery.isPending ? (
          <p className="flex items-center gap-2 text-sm text-ink-500">
            <Spinner /> Checking availability…
          </p>
        ) : quoteQuery.isError ? (
          <InlineError error={quoteQuery.error} />
        ) : quote && !quote.isAvailable ? (
          <div className="rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-700">
            Not available for these dates.
            {quote.unavailableDates.length > 0 && (
              <span className="mt-1 block text-xs">
                Taken: {quote.unavailableDates.slice(0, 4).join(', ')}
                {quote.unavailableDates.length > 4 && '…'}
              </span>
            )}
          </div>
        ) : quote ? (
          <dl className="space-y-1.5 text-sm">
            <Row
              label={`${formatMinor(quote.averageNightlyMinor, quote.currency, { compact: true })} × ${nights} night${nights === 1 ? '' : 's'}`}
              value={formatMinor(quote.accommodationMinor, quote.currency)}
            />
            {quote.extraGuestMinor > 0 && (
              <Row label="Extra guests" value={formatMinor(quote.extraGuestMinor, quote.currency)} />
            )}
            {quote.cleaningFeeMinor > 0 && (
              <Row label="Cleaning fee" value={formatMinor(quote.cleaningFeeMinor, quote.currency)} />
            )}
            <Row label="Taxes" value={formatMinor(quote.taxMinor, quote.currency)} />
            <div className="flex justify-between border-t border-ink-100 pt-2 font-semibold text-ink-900">
              <dt>Total</dt>
              <dd>{formatMinor(quote.totalMinor, quote.currency)}</dd>
            </div>
          </dl>
        ) : null}
      </div>

      <Button fullWidth size="lg" className="mt-4" disabled={!canReserve} onClick={reserve}>
        {stayValid ? 'Reserve' : 'Check availability'}
      </Button>
      <p className="mt-2 text-center text-xs text-ink-500">
        You will not be charged until the next step.
      </p>
      <p className="mt-3 text-center text-xs text-ink-500">
        {cancellationPolicy(property.cancellationPolicy).short}
      </p>
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

function DateInput({
  label,
  value,
  min,
  onChange,
}: {
  label: string
  value: string
  min: string
  onChange: (value: IsoDate) => void
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-600">{label}</span>
      <input
        type="date"
        value={value}
        min={min}
        onChange={(e) => onChange(e.target.value)}
        className="h-11 w-full rounded-xl border border-ink-200 px-2.5 text-sm"
      />
    </label>
  )
}

function NumberInput({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  onChange: (value: number) => void
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-600">{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        onChange={(e) => onChange(Math.min(max, Math.max(min, Number(e.target.value) || min)))}
        className={cn('h-11 w-full rounded-xl border border-ink-200 px-2.5 text-sm tabular-nums')}
      />
    </label>
  )
}
