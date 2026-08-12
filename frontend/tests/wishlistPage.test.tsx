/**
 * The wishlist page, rendered against fake repositories.
 *
 * The behaviour under test is the one the server was changed for: a saved
 * property whose host has taken it down stays on the list as a **tombstone**
 * rather than disappearing. A list that quietly gets shorter reads as a bug,
 * and the guest goes looking for the place they lost.
 *
 * No network and no fetch mock — an object literal satisfying the port. If
 * this file ever needs MSW, the seam has leaked.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { RepositoryProvider } from '@/application/RepositoryContext'
import type { Repositories } from '@/application/ports'
import type { WishlistEntry } from '@/domain/wishlist'
import WishlistPage from '@/pages/WishlistPage'

function entry(overrides: Partial<WishlistEntry> = {}): WishlistEntry {
  return {
    propertyId: 'p1',
    slug: 'sea-breeze-villa',
    name: 'Sea Breeze Villa',
    city: 'Anjuna',
    coverImageUrl: null,
    fromPriceMinor: 1_500_000,
    currency: 'INR',
    reviewAverage: 4.6,
    reviewCount: 82,
    savedAt: '2026-08-01T10:00:00Z',
    note: null,
    ...overrides,
  }
}

function renderPage(entries: readonly WishlistEntry[]) {
  // `Promise.resolve` rather than `async () =>`: these satisfy an async port
  // without awaiting anything, and the lint rule that flags a pointless
  // `async` is right to.
  const repositories = {
    wishlist: {
      list: vi.fn(() => Promise.resolve(entries)),
      add: vi.fn(() => Promise.resolve()),
      remove: vi.fn(() => Promise.resolve()),
      clear: vi.fn(() => Promise.resolve()),
    },
  } as unknown as Repositories

  // Retries off: a failing query would otherwise take three attempts before
  // the assertion sees the error state, and the test would look flaky.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })

  render(
    <QueryClientProvider client={client}>
      <RepositoryProvider repositories={repositories}>
        <MemoryRouter>
          <WishlistPage />
        </MemoryRouter>
      </RepositoryProvider>
    </QueryClientProvider>,
  )
  return repositories
}

describe('WishlistPage', () => {
  it('shows a saved property with its price', async () => {
    renderPage([entry()])

    expect(await screen.findByText('Sea Breeze Villa')).toBeInTheDocument()
    // ₹15,000 — rendered compactly, so the assertion is on the digits rather
    // than on ICU's choice of separator or symbol.
    await waitFor(() => {
      expect(screen.getByText(/15/)).toBeInTheDocument()
    })
  })

  it('keeps a delisted property on the list', async () => {
    /**
     * The tombstone. Dropping the row would leave the guest hunting for a
     * place they know they saved.
     */
    renderPage([entry({ available: false })])

    expect(await screen.findByText('Sea Breeze Villa')).toBeInTheDocument()
    expect(screen.getByText(/no longer available/i)).toBeInTheDocument()
  })

  it('does not link a delisted property', async () => {
    /** A link to a listing that has been taken down is a link to a 404. */
    renderPage([entry({ available: false })])

    await screen.findByText('Sea Breeze Villa')
    expect(screen.queryByRole('link', { name: /sea breeze villa/i })).toBeNull()
  })

  it('links a live property to its page', async () => {
    renderPage([entry()])

    const link = await screen.findByRole('link', { name: /sea breeze villa/i })
    expect(link).toHaveAttribute('href', '/stays/sea-breeze-villa')
  })

  it('shows no price for a delisted property', async () => {
    /**
     * A price on something nobody can book is a support ticket about why the
     * button does not work.
     */
    renderPage([entry({ available: false, fromPriceMinor: null })])

    await screen.findByText(/no longer available/i)
    expect(screen.queryByText(/night/i)).toBeNull()
  })

  it('renders a saved note', async () => {
    renderPage([entry({ note: 'for Ma — check step-free access' })])

    expect(await screen.findByText(/step-free access/)).toBeInTheDocument()
  })

  it('treats an entry with no availability flag as available', async () => {
    /**
     * `undefined` means a locally-saved entry, which has no way to know.
     * Only an explicit `false` from the server is a tombstone — otherwise
     * every signed-out save would render as unavailable.
     */
    // Built without the key at all rather than with `available: undefined` —
    // under `exactOptionalPropertyTypes` those are different things, and the
    // locally-saved entry genuinely lacks the key.
    const local = entry()
    delete (local as { available?: boolean }).available
    renderPage([local])

    await screen.findByText('Sea Breeze Villa')
    expect(screen.queryByText(/no longer available/i)).toBeNull()
  })

  it('shows an empty state rather than a blank page', async () => {
    renderPage([])

    // Something has to be on screen. A wishlist with nothing in it is the
    // normal state for most visitors.
    await waitFor(() => {
      expect(document.body.textContent?.trim().length).toBeGreaterThan(0)
    })
    expect(screen.queryByText('Sea Breeze Villa')).toBeNull()
  })
})
