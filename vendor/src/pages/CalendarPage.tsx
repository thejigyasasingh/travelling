import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useCalendar, useProperties, useSetAvailability, useSetRates } from '@/api/queries'
import { PageHeader } from '@/app/Shell'
import { formatMinor } from '@/core/format'
import { ApiError } from '@/core/http'
import { Button, Card, Spinner, cn } from '@/ui/primitives'
import type { CalendarDay } from '@/api/types'

/**
 * Pricing and availability, on one screen.
 *
 * Deliberately not two screens. A host raising the New Year rate is also
 * closing the 31st and setting a three-night minimum, and splitting those into
 * separate pages means doing the same date arithmetic three times and being
 * unable to see the result of the first change while making the second.
 *
 * Everything is a *range* edit. A calendar that only edits one night at a time
 * is a calendar nobody uses for a season.
 */
export function CalendarPage() {
  const [params, setParams] = useSearchParams()
  const { data: properties } = useProperties({ size: 100 })

  const propertyId = params.get('property') ?? properties?.items[0]?.id ?? ''
  const property = properties?.items.find((candidate) => candidate.id === propertyId)
  const roomId = params.get('room') ?? property?.room_types[0]?.id ?? ''

  const [from, setFrom] = useState(() => today())
  const [to, setTo] = useState(() => addDays(today(), 59))

  const { data: calendar, isPending, isFetching } = useCalendar(propertyId, roomId, from, to)

  // A room from a previously selected property would 404. Clearing it here
  // lets the default-to-first-room path pick a valid one.
  useEffect(() => {
    if (!property || !roomId) return
    if (!property.room_types.some((room) => room.id === roomId)) {
      const next = new URLSearchParams(params)
      next.delete('room')
      setParams(next, { replace: true })
    }
  }, [property, roomId, params, setParams])

  const [selection, setSelection] = useState<Set<string>>(new Set())
  const selected = useMemo(() => [...selection].sort(), [selection])

  function choose(key: 'property' | 'room', value: string) {
    const next = new URLSearchParams(params)
    next.set(key, value)
    if (key === 'property') next.delete('room')
    setParams(next, { replace: true })
    setSelection(new Set())
  }

  return (
    <>
      <PageHeader
        title="Calendar & pricing"
        description="Select nights, then set a price or close them. Everything applies to the whole selection."
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="text-sm">
          <span className="block text-xs font-medium text-ink-600">Property</span>
          <select
            value={propertyId}
            onChange={(event) => choose('property', event.target.value)}
            className="mt-1 h-9 rounded-lg border border-ink-200 bg-white px-2 text-sm"
          >
            {properties?.items.map((candidate) => (
              <option key={candidate.id} value={candidate.id}>
                {candidate.name}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm">
          <span className="block text-xs font-medium text-ink-600">Room</span>
          <select
            value={roomId}
            onChange={(event) => choose('room', event.target.value)}
            className="mt-1 h-9 rounded-lg border border-ink-200 bg-white px-2 text-sm"
          >
            {property?.room_types.map((room) => (
              <option key={room.id} value={room.id}>
                {room.name}
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm">
          <span className="block text-xs font-medium text-ink-600">From</span>
          <input
            type="date"
            value={from}
            onChange={(event) => setFrom(event.target.value)}
            className="mt-1 h-9 rounded-lg border border-ink-200 px-2 text-sm"
          />
        </label>
        <label className="text-sm">
          <span className="block text-xs font-medium text-ink-600">To</span>
          <input
            type="date"
            value={to}
            onChange={(event) => setTo(event.target.value)}
            className="mt-1 h-9 rounded-lg border border-ink-200 px-2 text-sm"
          />
        </label>

        {isFetching && <Spinner className="mb-2 text-ink-400" />}
      </div>

      {!property?.room_types.length ? (
        <Card>
          <p className="px-4 py-12 text-center text-sm text-ink-500">
            This listing has no rooms yet. Add one before setting rates.
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
          <Card
            title={calendar?.room_type_name ?? 'Nights'}
            action={
              selected.length > 0 ? (
                <button
                  type="button"
                  onClick={() => setSelection(new Set())}
                  className="text-xs text-brand-700 underline"
                >
                  Clear {selected.length} selected
                </button>
              ) : (
                <span className="text-xs text-ink-500">Click nights to select</span>
              )
            }
          >
            {isPending ? (
              <div className="grid place-items-center py-20">
                <Spinner />
              </div>
            ) : (
              <Grid
                days={calendar?.days ?? []}
                currency={calendar?.currency ?? 'INR'}
                selection={selection}
                onToggle={(date) =>
                  setSelection((current) => {
                    const next = new Set(current)
                    if (next.has(date)) next.delete(date)
                    else next.add(date)
                    return next
                  })
                }
              />
            )}
          </Card>

          <EditPanel
            propertyId={propertyId}
            roomId={roomId}
            selected={selected}
            onApplied={() => setSelection(new Set())}
          />
        </div>
      )}
    </>
  )
}

// ══════════════════════════════════════════════════════════════════════════

function Grid({
  days,
  currency,
  selection,
  onToggle,
}: {
  days: CalendarDay[]
  currency: string
  selection: Set<string>
  onToggle: (date: string) => void
}) {
  if (days.length === 0) {
    return <p className="px-4 py-12 text-center text-sm text-ink-500">No nights in this range.</p>
  }

  return (
    <div className="grid grid-cols-2 gap-1.5 p-3 sm:grid-cols-4 lg:grid-cols-7">
      {days.map((day) => {
        const isSelected = selection.has(day.date)
        const soldOut = day.units_available === 0 && !day.is_blocked
        return (
          <button
            key={day.date}
            type="button"
            onClick={() => onToggle(day.date)}
            aria-pressed={isSelected}
            className={cn(
              'rounded-lg border p-2 text-left text-xs transition-colors',
              isSelected
                ? 'border-brand-500 bg-brand-50 ring-1 ring-brand-500'
                : day.is_blocked
                  ? 'border-ink-200 bg-ink-100 text-ink-400'
                  : soldOut
                    ? 'border-good-200 bg-good-50'
                    : 'border-ink-200 bg-white hover:bg-ink-50',
            )}
          >
            <span className="block font-medium text-ink-700">{dayLabel(day.date)}</span>
            <span
              className={cn(
                'mt-1 block tabular-nums',
                // A rate nobody has set is shown lighter than one that was
                // chosen. "₹6,000 because I decided" and "₹6,000 because
                // nobody has touched December" are different facts.
                day.is_default ? 'text-ink-400' : 'font-medium text-ink-900',
              )}
            >
              {formatMinor(day.rate_minor, currency, { compact: true })}
            </span>
            <span className="mt-0.5 block text-ink-500">
              {day.is_blocked
                ? 'Closed'
                : `${day.units_available}/${day.units_total} left`}
            </span>
          </button>
        )
      })}
    </div>
  )
}

/**
 * What to do with the selected nights.
 *
 * Rates and availability are separate PUTs on the server, and this panel keeps
 * them separate rather than sending one combined save: a host who only meant to
 * close a date should not have their prices rewritten because a rate field
 * still held a value from the last edit.
 */
function EditPanel({
  propertyId,
  roomId,
  selected,
  onApplied,
}: {
  propertyId: string
  roomId: string
  selected: string[]
  onApplied: () => void
}) {
  const rates = useSetRates(propertyId, roomId)
  const availability = useSetAvailability(propertyId, roomId)

  const [rateRupees, setRateRupees] = useState('')
  const [minNights, setMinNights] = useState('')
  const [units, setUnits] = useState('')

  const from = selected[0]
  const lastNight = selected[selected.length - 1]
  const contiguous = selected.length > 0 && spanDays(from!, lastNight!) === selected.length

  /**
   * The nights→range translation, and the only place it happens.
   *
   * Every date range in this system is half-open, stays included: a booking
   * from the 5th to the 8th is three nights, 5–7. The calendar deals in nights
   * directly, so the last night selected has to become the day *after* it here.
   *
   * Two things break without this, and both are silent. Selecting 24–31
   * December and setting a New Year rate would leave the 31st — the most
   * valuable night of the year — at the default price. And a single night
   * would send `from === to`, which the server rejects outright, making the
   * commonest calendar edit impossible.
   */
  const to = lastNight ? addDays(lastNight, 1) : undefined

  if (selected.length === 0) {
    return (
      <Card title="No nights selected">
        <p className="px-4 py-6 text-sm text-ink-500">
          Click nights in the calendar to select them. Changes apply to everything selected at once.
        </p>
      </Card>
    )
  }

  // The server takes a date *range*, so a selection with gaps in it cannot be
  // sent as one call without silently changing nights the host did not pick.
  // Saying so beats quietly applying it to the gaps.
  const error = rates.error ?? availability.error
  const busy = rates.isPending || availability.isPending

  return (
    <Card title={`${selected.length} night${selected.length === 1 ? '' : 's'} selected`}>
      <div className="space-y-4 px-4 py-3">
        <p className="text-xs text-ink-500">
          {from === lastNight ? dayLabel(from!) : `${dayLabel(from!)} — ${dayLabel(lastNight!)}`}
        </p>

        {!contiguous && (
          <p role="alert" className="rounded-lg bg-warn-50 px-3 py-2 text-xs text-warn-700">
            Your selection has gaps. Changes apply to the whole range from {dayLabel(from!)} to{' '}
            {dayLabel(lastNight!)}, including the nights you did not pick.
          </p>
        )}

        <div>
          <h3 className="text-xs font-semibold tracking-wide text-ink-700 uppercase">Price</h3>
          <div className="mt-2 space-y-2">
            <label className="block text-sm">
              <span className="text-xs text-ink-600">Nightly rate (₹)</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={rateRupees}
                onChange={(event) => setRateRupees(event.target.value)}
                className="mt-1 h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
              />
            </label>
            <label className="block text-sm">
              <span className="text-xs text-ink-600">Minimum nights</span>
              <input
                type="number"
                min={1}
                max={90}
                value={minNights}
                onChange={(event) => setMinNights(event.target.value)}
                placeholder="unchanged"
                className="mt-1 h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
              />
            </label>
            <Button
              variant="primary"
              className="w-full"
              disabled={busy || (!rateRupees && !minNights)}
              onClick={() =>
                rates.mutate(
                  {
                    from_date: from!,
                    to_date: to!,
                    ...(rateRupees ? { rate_minor: Math.round(Number(rateRupees) * 100) } : {}),
                    ...(minNights ? { min_nights: Number(minNights) } : {}),
                  },
                  { onSuccess: onApplied },
                )
              }
            >
              {rates.isPending ? 'Applying…' : 'Apply price'}
            </Button>
          </div>
        </div>

        <div className="border-t border-ink-100 pt-4">
          <h3 className="text-xs font-semibold tracking-wide text-ink-700 uppercase">
            Availability
          </h3>
          <div className="mt-2 space-y-2">
            <label className="block text-sm">
              <span className="text-xs text-ink-600">Units on sale</span>
              <input
                type="number"
                min={0}
                max={500}
                value={units}
                onChange={(event) => setUnits(event.target.value)}
                placeholder="unchanged"
                className="mt-1 h-9 w-full rounded-lg border border-ink-200 px-2 text-sm"
              />
            </label>
            <div className="flex gap-2">
              <Button
                className="flex-1"
                disabled={busy}
                onClick={() =>
                  availability.mutate(
                    {
                      from_date: from!,
                      to_date: to!,
                      is_blocked: true,
                      ...(units ? { units_total: Number(units) } : {}),
                    },
                    { onSuccess: onApplied },
                  )
                }
              >
                Close
              </Button>
              <Button
                className="flex-1"
                disabled={busy}
                onClick={() =>
                  availability.mutate(
                    {
                      from_date: from!,
                      to_date: to!,
                      is_blocked: false,
                      ...(units ? { units_total: Number(units) } : {}),
                    },
                    { onSuccess: onApplied },
                  )
                }
              >
                Open
              </Button>
            </div>
            <p className="text-xs text-ink-500">
              Closing a night stops new bookings. It never cancels a booking already taken — if a
              night is already sold, reduce units and the guests who booked keep their room.
            </p>
          </div>
        </div>

        {error instanceof ApiError && (
          <p role="alert" className="rounded-lg bg-bad-50 px-3 py-2 text-sm text-bad-700">
            {error.message}
          </p>
        )}
      </div>
    </Card>
  )
}

// ── dates ─────────────────────────────────────────────────────────────────
//
// All plain `YYYY-MM-DD`, parsed as UTC and never as local. A calendar that
// shifts by a day for a host in a negative offset is a calendar that prices the
// wrong night.

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

function addDays(iso: string, days: number): string {
  return new Date(Date.parse(`${iso}T00:00:00Z`) + days * 86_400_000).toISOString().slice(0, 10)
}

function spanDays(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000) + 1
}

function dayLabel(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    weekday: 'short',
    timeZone: 'UTC',
  })
}
