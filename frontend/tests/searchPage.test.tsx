/**
 * Search results, rendered against fake repositories.
 *
 * This is what the ports layer buys: a page test with **no network, no MSW and
 * no mocking of `fetch`** — just an object literal that satisfies the
 * interface. If this file ever needs a fetch mock, the seam has leaked.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { RepositoryProvider } from '@/application/RepositoryContext'
import type { Repositories, SearchCriteria } from '@/application/ports'
import type { SearchResultItem } from '@/domain/property'
import SearchPage from '@/pages/SearchPage'

function item(overrides: Partial<SearchResultItem> = {}): SearchResultItem {
  return {
    id: 'p1',
    slug: 'sea-breeze-villa',
    name: 'Sea Breeze Villa',
    propertyType: 'villa',
    city: 'Anjuna',
    countryCode: 'IN',
    latitude: 15.57,
    longitude: 73.74,
    distanceM: null,
    coverImageUrl: null,
    reviewAverage: 4.6,
    reviewCount: 82,
    amenityCodes: ['wifi'],
    instantBooking: true,
    cancellationPolicy: 'moderate',
    maxOccupancy: 6,
    fromPriceMinor: 1_500_000,
    totalPriceMinor: null,
    currency: 'INR',
    isAvailable: true,
    ...overrides,
  }
}

function renderSearch(
  items: SearchResultItem[],
  {
    route = '/search',
    onSearch,
  }: { route?: string; onSearch?: (criteria: SearchCriteria) => void } = {},
) {
  const repositories = {
    catalog: {
      search: (criteria: SearchCriteria) => {
        onSearch?.(criteria)
        return Promise.resolve({
          items,
          nextCursor: null,
          totalEstimate: items.length,
          appliedRadiusM: null,
        })
      },
      suggest: () => Promise.resolve([]),
      amenities: () => Promise.resolve([]),
    },
    wishlist: { list: () => Promise.resolve([]) },
  } as unknown as Repositories

  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  return render(
    <MemoryRouter initialEntries={[route]}>
      <RepositoryProvider repositories={repositories}>
        <QueryClientProvider client={queryClient}>
          <SearchPage />
        </QueryClientProvider>
      </RepositoryProvider>
    </MemoryRouter>,
  )
}

describe('SearchPage', () => {
  it('lists the stays it was given', async () => {
    renderSearch([item(), item({ id: 'p2', slug: 'hill-house', name: 'Hill House' })])

    expect(await screen.findByRole('heading', { name: 'Sea Breeze Villa' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Hill House' })).toBeInTheDocument()
  })

  it('labels a dateless price as a nightly "from" rate', async () => {
    // Without dates there is no stay total, and showing a nightly rate as if it
    // were the total is the oldest dark pattern in travel booking.
    renderSearch([item()])

    expect(await screen.findByText('from')).toBeInTheDocument()
    expect(screen.getByText('₹15,000')).toBeInTheDocument()
    expect(screen.getByText('/ night')).toBeInTheDocument()
  })

  it('labels a dated price as the stay total', async () => {
    renderSearch([item({ totalPriceMinor: 3_360_000 })], {
      route: '/search?check_in=2026-09-12&check_out=2026-09-14',
    })

    expect(await screen.findByText('₹33,600')).toBeInTheDocument()
    expect(screen.getByText(/total · 2 nights/)).toBeInTheDocument()
  })

  it('reads its criteria from the URL, so a filtered search is shareable', async () => {
    const seen = vi.fn()
    renderSearch([item()], {
      route: '/search?q=Goa&check_in=2026-09-12&check_out=2026-09-14&adults=4&type=villa&amenity=wifi&min_rating=4.5',
      onSearch: seen,
    })

    await waitFor(() => expect(seen).toHaveBeenCalled())
    expect(seen).toHaveBeenCalledWith(
      expect.objectContaining({
        q: 'Goa',
        checkIn: '2026-09-12',
        checkOut: '2026-09-14',
        adults: 4,
        propertyType: ['villa'],
        amenity: ['wifi'],
        minRating: 4.5,
      }),
    )
  })

  it('shows a way out when nothing matches, not a blank page', async () => {
    renderSearch([])

    expect(await screen.findByText('No stays match those filters')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Clear filters' })).toBeInTheDocument()
  })

  it('marks a sold-out stay rather than quietly hiding it', async () => {
    renderSearch([item({ isAvailable: false })], {
      route: '/search?check_in=2026-09-12&check_out=2026-09-14',
    })

    expect(await screen.findByText('Sold out for these dates')).toBeInTheDocument()
  })
})
