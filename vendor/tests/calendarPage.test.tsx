/**
 * The calendar and pricing screen.
 *
 * The riskiest screen in the portal: everything on it is a **range** edit, and
 * a host who thinks they closed one night but closed a fortnight loses a
 * fortnight of bookings. So the tests are about what the host is told before
 * they press the button, not about the request that follows.
 *
 * The specific hazard is a non-contiguous selection. The server takes a
 * `from_date`/`to_date` range, so picking Friday and Sunday applies to
 * Saturday too — and the screen has to say so.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { CalendarPage } from '@/pages/CalendarPage'
import type { Calendar, CalendarDay, Page, VendorProperty } from '@/api/types'

const PROPERTY_ID = '11111111-1111-1111-1111-111111111111'
const ROOM_ID = '22222222-2222-2222-2222-222222222222'

function day(date: string, overrides: Partial<CalendarDay> = {}): CalendarDay {
  return {
    date,
    units_total: 3,
    units_booked: 0,
    units_available: 3,
    is_blocked: false,
    rate_minor: 450_000,
    rate_source: 'default',
    min_nights: 1,
    is_default: true,
    ...overrides,
  }
}

const PROPERTY = {
  id: PROPERTY_ID,
  slug: 'test-house',
  name: 'The Test House',
  property_type: 'villa',
  status: 'published',
  city: 'Anjuna',
  room_types: [{ id: ROOM_ID, name: 'Garden Room' }],
} as unknown as VendorProperty

const CALENDAR: Calendar = {
  room_type_id: ROOM_ID,
  room_type_name: 'Garden Room',
  currency: 'INR',
  from_date: '2026-09-01',
  to_date: '2026-09-05',
  days: [
    day('2026-09-01'),
    day('2026-09-02', { is_default: false, rate_minor: 600_000 }),
    day('2026-09-03', { is_blocked: true }),
    day('2026-09-04', { units_available: 0, units_booked: 3 }),
    day('2026-09-05'),
  ],
}

// Typed, so `mock.calls` is not `any[]` and destructuring a payload is safe.
const setRates = vi.fn<(payload: Record<string, unknown>) => void>()
const setAvailability = vi.fn<(payload: Record<string, unknown>) => void>()

vi.mock('@/api/queries', () => ({
  useProperties: () => ({
    data: {
      items: [PROPERTY],
      total: 1,
      page: 1,
      size: 20,
    } as Page<VendorProperty>,
  }),
  useCalendar: () => ({ data: CALENDAR, isPending: false, isFetching: false }),
  useSetRates: () => ({ mutate: setRates, isPending: false, error: null }),
  useSetAvailability: () => ({
    mutate: setAvailability,
    isPending: false,
    error: null,
  }),
}))

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/calendar?property=${PROPERTY_ID}&room=${ROOM_ID}`]}>
        <CalendarPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  setRates.mockClear()
  setAvailability.mockClear()
})

describe('CalendarPage', () => {
  it('renders a night per day in the range', async () => {
    renderPage()

    // Five nights, each its own toggle.
    await waitFor(() => {
      expect(screen.getAllByRole('button', { pressed: false }).length).toBeGreaterThanOrEqual(5)
    })
  })

  it('shows how many units are left on each night', async () => {
    renderPage()

    // Three of the five nights are wide open, so this matches more than once.
    expect((await screen.findAllByText('3/3 left')).length).toBe(3)
    expect(screen.getByText('0/3 left')).toBeInTheDocument()
  })

  it('marks a closed night as closed rather than sold out', async () => {
    /**
     * Two different states a host acts on differently: "I closed this" and
     * "this sold". Rendering both the same way loses a decision they made.
     */
    renderPage()

    expect(await screen.findByText('Closed')).toBeInTheDocument()
  })

  it('prompts before anything is selected', async () => {
    renderPage()

    expect(await screen.findByText(/no nights selected/i)).toBeInTheDocument()
  })

  it('counts the selection', async () => {
    const user = userEvent.setup()
    renderPage()

    const nights = await screen.findAllByRole('button', { pressed: false })
    await user.click(nights[0]!)

    expect(await screen.findByText(/1 night selected/i)).toBeInTheDocument()
  })

  it('warns when the selection has gaps', async () => {
    /**
     * **The** warning on this screen.
     *
     * The server takes a date *range*. Selecting the 1st and the 3rd applies
     * to the 2nd as well — which a host reading "2 nights selected" would
     * never guess. Silently pricing a night they did not choose is how a
     * season gets mispriced.
     */
    const user = userEvent.setup()
    renderPage()

    const nights = await screen.findAllByRole('button', { pressed: false })
    await user.click(nights[0]!)
    await user.click(nights[2]!)

    expect(await screen.findByText(/gaps/i)).toBeInTheDocument()
  })

  it('does not warn when the selection is contiguous', async () => {
    const user = userEvent.setup()
    renderPage()

    const nights = await screen.findAllByRole('button', { pressed: false })
    await user.click(nights[0]!)
    await user.click(nights[1]!)

    await screen.findByText(/2 nights selected/i)
    expect(screen.queryByText(/gaps/i)).toBeNull()
  })

  it('sends a price for the selected nights as a half-open range', async () => {
    /**
     * **The** off-by-one on this screen.
     *
     * The server's `DateRange` is half-open — `[start, end)` — matching the
     * Postgres `daterange` with a `'[)'` bound that the booking exclusion
     * constraint uses, and it refuses `to_date <= from_date` outright. So two
     * selected nights (1st and 2nd) send `to_date` as the **3rd**, and a
     * single selected night still sends a range a day wide.
     *
     * Written down here because it looks like a bug and someone will
     * eventually "fix" it into one: sending the last night as `to_date` would
     * silently drop the final night from every rate edit, and make a
     * one-night edit fail validation.
     */
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: /1 Sept/ }))
    await user.click(screen.getByRole('button', { name: /2 Sept/ }))

    await user.type(screen.getByLabelText(/nightly rate/i), '5500')
    await user.click(screen.getByRole('button', { name: /apply price/i }))

    expect(setRates).toHaveBeenCalledOnce()
    const [payload] = setRates.mock.calls[0]!
    // Rupees in the form, paise on the wire.
    expect(payload.rate_minor).toBe(550_000)
    expect(payload.from_date).toBe('2026-09-01')
    expect(payload.to_date).toBe('2026-09-03')
  })

  it('sends a one-day-wide range for a single night', async () => {
    /** `to_date == from_date` is refused by the server. */
    const user = userEvent.setup()
    renderPage()

    await user.click(await screen.findByRole('button', { name: /1 Sept/ }))
    await user.type(screen.getByLabelText(/nightly rate/i), '5000')
    await user.click(screen.getByRole('button', { name: /apply price/i }))

    const [payload] = setRates.mock.calls[0]!
    expect(payload.from_date).toBe('2026-09-01')
    expect(payload.to_date).toBe('2026-09-02')
  })

  it('will not apply a price with nothing filled in', async () => {
    /** An empty form that submits sends `rate_minor: NaN`. */
    const user = userEvent.setup()
    renderPage()

    const nights = await screen.findAllByRole('button', { pressed: false })
    await user.click(nights[0]!)

    const apply = await screen.findByRole('button', { name: /apply price/i })
    expect(apply).toBeDisabled()
  })

  it('closes a range without touching its price', async () => {
    /**
     * Rates and availability are separate calls on purpose: a host who only
     * meant to close a date must not have their prices rewritten because a
     * rate field still held a value from the last edit.
     */
    const user = userEvent.setup()
    renderPage()

    const nights = await screen.findAllByRole('button', { pressed: false })
    await user.click(nights[0]!)
    await user.type(screen.getByLabelText(/nightly rate/i), '9999')
    await user.click(screen.getByRole('button', { name: /^close$/i }))

    expect(setAvailability).toHaveBeenCalledOnce()
    expect(setAvailability.mock.calls[0]![0].is_blocked).toBe(true)
    expect(setRates).not.toHaveBeenCalled()
  })

  it('says that closing a night does not cancel bookings', async () => {
    /**
     * "Close" reads as "cancel" to someone doing it for the first time. The
     * screen says otherwise before they press it.
     */
    const user = userEvent.setup()
    renderPage()

    const nights = await screen.findAllByRole('button', { pressed: false })
    await user.click(nights[0]!)

    expect(await screen.findByText(/never cancels a booking already taken/i)).toBeInTheDocument()
  })
})
