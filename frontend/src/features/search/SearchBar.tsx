/**
 * The search bar: destination, dates, guests.
 *
 * One component for the hero and the results header, because the two must
 * behave identically — a guest who types a city on the home page and again on
 * the results page should not meet two different widgets.
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSuggestions } from '@/application/hooks/useCatalog'
import { paramsFromCriteria } from '@/application/hooks/useSearchParamsState'
import type { SearchCriteria } from '@/application/ports'
import { addDays, today, type IsoDate } from '@/core/dates'
import { Button } from '@/ui/Button'
import { cn } from '@/ui/cn'

interface Props {
  initial?: SearchCriteria
  variant?: 'hero' | 'compact'
  onSubmit?: (criteria: SearchCriteria) => void
}

export function SearchBar({ initial = {}, variant = 'hero', onSubmit }: Props) {
  const navigate = useNavigate()
  const [q, setQ] = useState(initial.q ?? '')
  const [cityId, setCityId] = useState(initial.cityId)
  // '' means "not chosen" — what an empty <input type=date> reports.
  const [checkIn, setCheckIn] = useState<IsoDate>(initial.checkIn ?? '')
  const [checkOut, setCheckOut] = useState<IsoDate>(initial.checkOut ?? '')
  const [adults, setAdults] = useState(initial.adults ?? 2)
  const [children, setChildren] = useState(initial.children ?? 0)
  const [rooms, setRooms] = useState(initial.rooms ?? 1)
  const [showSuggestions, setShowSuggestions] = useState(false)

  const { data: suggestions = [] } = useSuggestions(q)
  const containerRef = useRef<HTMLFormElement>(null)

  useEffect(() => {
    function onPointerDown(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setShowSuggestions(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [])

  function submit(event: React.FormEvent) {
    event.preventDefault()
    const criteria: SearchCriteria = {
      ...(q ? { q } : {}),
      ...(cityId ? { cityId } : {}),
      ...(checkIn ? { checkIn } : {}),
      ...(checkOut ? { checkOut } : {}),
      adults,
      ...(children ? { children } : {}),
      rooms,
    }
    if (onSubmit) onSubmit(criteria)
    else void navigate({ pathname: '/search', search: paramsFromCriteria(criteria).toString() })
  }

  const hero = variant === 'hero'
  const minCheckOut = checkIn ? addDays(checkIn, 1) : addDays(today(), 1)

  return (
    <form
      ref={containerRef}
      onSubmit={submit}
      role="search"
      aria-label="Find a stay"
      className={cn(
        'rounded-2xl bg-white',
        hero ? 'p-3 shadow-lift md:p-4' : 'border border-ink-200 p-2 shadow-sm',
      )}
    >
      <div className={cn('grid gap-2', hero ? 'md:grid-cols-[2fr_1fr_1fr_auto]' : 'md:grid-cols-[2fr_1fr_1fr_auto]')}>
        <div className="relative">
          <label htmlFor="search-destination" className="sr-only">
            Destination
          </label>
          <input
            id="search-destination"
            type="search"
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              // Typing after picking a suggestion means the guest changed their
              // mind; keeping the old city id would search the wrong place.
              setCityId(undefined)
              setShowSuggestions(true)
            }}
            onFocus={() => setShowSuggestions(true)}
            placeholder="Where to? Goa, Manali, Jaipur…"
            autoComplete="off"
            className="h-12 w-full rounded-xl border border-ink-200 px-4 text-sm placeholder:text-ink-400 focus:border-brand-500"
            aria-autocomplete="list"
            aria-expanded={showSuggestions && suggestions.length > 0}
            aria-controls="search-suggestions"
          />
          {showSuggestions && suggestions.length > 0 && (
            <ul
              id="search-suggestions"
              role="listbox"
              className="absolute top-full left-0 z-50 mt-1 w-full overflow-hidden rounded-xl border border-ink-200 bg-white shadow-lift"
            >
              {suggestions.map((s) => (
                <li key={`${s.kind}-${s.id}`}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={false}
                    onClick={() => {
                      setQ(s.label)
                      setCityId(s.kind === 'city' ? s.id : undefined)
                      setShowSuggestions(false)
                      // A property suggestion is a specific stay, so go
                      // straight there rather than searching for its name.
                      if (s.kind === 'property') void navigate(`/stays/${s.slug}`)
                    }}
                    className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-ink-50"
                  >
                    <span className="text-ink-400">{s.kind === 'city' ? '◎' : '⌂'}</span>
                    <span>
                      <span className="block text-sm text-ink-800">{s.label}</span>
                      {s.sublabel && <span className="block text-xs text-ink-500">{s.sublabel}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <label htmlFor="search-check-in" className="sr-only">
            Check in
          </label>
          <input
            id="search-check-in"
            type="date"
            value={checkIn}
            min={today()}
            onChange={(e) => {
              const value = e.target.value
              setCheckIn(value)
              // Keep the range valid rather than letting the server reject it.
              if (checkOut && value >= checkOut) setCheckOut(addDays(value, 1))
            }}
            className="h-12 w-full rounded-xl border border-ink-200 px-3 text-sm focus:border-brand-500"
          />
        </div>

        <div>
          <label htmlFor="search-check-out" className="sr-only">
            Check out
          </label>
          <input
            id="search-check-out"
            type="date"
            value={checkOut}
            min={minCheckOut}
            onChange={(e) => setCheckOut(e.target.value)}
            className="h-12 w-full rounded-xl border border-ink-200 px-3 text-sm focus:border-brand-500"
          />
        </div>

        <Button type="submit" size="lg" className="md:px-8">
          Search
        </Button>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-3 px-1">
        <GuestStepper label="Adults" value={adults} min={1} max={16} onChange={setAdults} />
        <GuestStepper label="Children" value={children} min={0} max={10} onChange={setChildren} />
        <GuestStepper label="Rooms" value={rooms} min={1} max={8} onChange={setRooms} />
      </div>
    </form>
  )
}

function GuestStepper({
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
    <div className="flex items-center gap-1.5">
      <span className="text-xs font-medium text-ink-600">{label}</span>
      <div className="flex items-center rounded-lg border border-ink-200">
        <button
          type="button"
          onClick={() => onChange(Math.max(min, value - 1))}
          disabled={value <= min}
          aria-label={`Fewer ${label.toLowerCase()}`}
          className="grid size-7 place-items-center text-ink-600 disabled:opacity-30"
        >
          −
        </button>
        {/* Announced as a live value so a screen reader hears the new count. */}
        <span className="min-w-6 text-center text-sm font-medium tabular-nums" aria-live="polite">
          {value}
        </span>
        <button
          type="button"
          onClick={() => onChange(Math.min(max, value + 1))}
          disabled={value >= max}
          aria-label={`More ${label.toLowerCase()}`}
          className="grid size-7 place-items-center text-ink-600 disabled:opacity-30"
        >
          +
        </button>
      </div>
    </div>
  )
}
