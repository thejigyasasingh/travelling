/**
 * The review repository, against payloads captured from the running server.
 *
 * These fixtures are verbatim responses, not invented ones. That is the point:
 * every mapping bug this project has shipped came from a hand-written fixture
 * agreeing with a hand-written mapper while both disagreed with the server —
 * `/auth/refresh` returning `{tokens, user}` rather than a flat token was
 * exactly that, and the test fixture had encoded the same wrong shape.
 *
 * So when the server changes, the honest way to update this file is to capture
 * the new response, not to adjust the expectation until it passes.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { reviewRepository } from '@/infrastructure/api/reviews'

// ── captured from GET /reviews/property/{id}?sort=recent&page=1&size=20 ────
const PROPERTY_PAYLOAD = {
  items: [
    {
      id: '019fdc11-27b0-7e31-a460-68903018edf3',
      property_id: '019fd748-8575-7483-85eb-62486a8becf7',
      rating: 4,
      title: 'Road noise',
      body: 'Updating: the host moved us to the garden-side room on night two.',
      categories: {},
      author_name: 'Dev Iyer',
      published_at: '2026-08-07T11:52:19.632720Z',
      edited_at: '2026-08-07T11:56:01.434156Z',
      host_reply: null,
      host_replied_at: null,
      moderation: 'published',
      can_edit: false,
    },
    {
      id: '019fdc05-43f7-7963-b288-a568670b0e9e',
      property_id: '019fd748-8575-7483-85eb-62486a8becf7',
      rating: 5,
      title: 'Quiet mornings by the water',
      body: 'The villa was spotless and the host left a note.',
      categories: { value: 4, accuracy: 4, location: 5, cleanliness: 5, communication: 5 },
      author_name: 'Rhea Menon',
      published_at: '2026-08-07T11:39:20.439527Z',
      edited_at: null,
      host_reply: 'Thank you Rhea. The bakery is our favourite too.',
      host_replied_at: '2026-08-07T11:51:32.942456Z',
      moderation: 'flagged',
      can_edit: false,
    },
  ],
  total: 2,
  page: 1,
  size: 20,
  average: 4.5,
  distribution: { '1': 0, '2': 0, '3': 0, '4': 1, '5': 1 },
}

/** The URL a `fetch` was called with, whatever form the first argument took. */
function urlOf(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  return input instanceof URL ? input.href : input.url
}

/** The JSON body, or `{}` for a request that had none. */
function bodyOf(init?: RequestInit): Record<string, unknown> {
  return typeof init?.body === 'string'
    ? (JSON.parse(init.body) as Record<string, unknown>)
    : {}
}

function mockFetch(payload: unknown, capture?: (url: string, init?: RequestInit) => void) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      capture?.(urlOf(input), init)
      return Promise.resolve(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('forProperty', () => {
  it('maps the server payload onto the domain type', async () => {
    mockFetch(PROPERTY_PAYLOAD)
    const page = await reviewRepository.forProperty('p1', {})

    expect(page.items).toHaveLength(2)
    const [recent, older] = page.items
    expect(recent?.authorName).toBe('Dev Iyer')
    expect(recent?.rating).toBe(4)
    expect(older?.hostReply).toEqual({
      body: 'Thank you Rhea. The bakery is our favourite too.',
      repliedAt: '2026-08-07T11:51:32.942456Z',
    })
  })

  it('leaves hostReply null when only one half is present', () => {
    // `host_reply` and `host_replied_at` are separate columns with a CHECK
    // tying them together, but a client that trusts one without the other
    // renders "replied on undefined".
    expect(
      PROPERTY_PAYLOAD.items[0]?.host_reply === null &&
        PROPERTY_PAYLOAD.items[0]?.host_replied_at === null,
    ).toBe(true)
  })

  it('reports no next page when the results fit on one', async () => {
    mockFetch(PROPERTY_PAYLOAD)
    const page = await reviewRepository.forProperty('p1', {})
    expect(page.nextCursor).toBeNull()
  })

  it('offers the next page number when more remain', async () => {
    mockFetch({ ...PROPERTY_PAYLOAD, total: 45 })
    const page = await reviewRepository.forProperty('p1', {})
    expect(page.nextCursor).toBe('2')
  })

  it('follows a cursor to the right page', async () => {
    let seen = ''
    mockFetch({ ...PROPERTY_PAYLOAD, page: 3, total: 100 }, (url) => {
      seen = url
    })
    await reviewRepository.forProperty('p1', { cursor: '3' })

    expect(seen).toContain('page=3')
    expect(seen).toContain('sort=recent')
  })

  it('passes the sort through', async () => {
    let seen = ''
    mockFetch(PROPERTY_PAYLOAD, (url) => {
      seen = url
    })
    await reviewRepository.forProperty('p1', { sort: 'rating_asc' })
    expect(seen).toContain('sort=rating_asc')
  })

  it('takes the count from total, not from the page length', async () => {
    // The summary drives "based on N reviews". Reading it off `items.length`
    // would say "based on 20 reviews" on any property with more than a page.
    mockFetch({ ...PROPERTY_PAYLOAD, total: 137 })
    const page = await reviewRepository.forProperty('p1', {})

    expect(page.summary.count).toBe(137)
    expect(page.summary.average).toBe(4.5)
  })

  it('keys the distribution by number, not by the string the server sends', async () => {
    // JSON object keys are strings. A component doing `distribution[5]` on
    // `{"5": 1}` gets undefined and renders an empty bar.
    mockFetch(PROPERTY_PAYLOAD)
    const page = await reviewRepository.forProperty('p1', {})

    expect(page.summary.distribution[5]).toBe(1)
    expect(page.summary.distribution[4]).toBe(1)
  })

  it('averages category scores across the reviews that gave them', async () => {
    // One review here has no categories at all. Including it in the
    // denominator would drag every category score towards zero.
    mockFetch(PROPERTY_PAYLOAD)
    const page = await reviewRepository.forProperty('p1', {})

    expect(page.summary.categoryAverages['cleanliness']).toBe(5)
    expect(page.summary.categoryAverages['value']).toBe(4)
  })

  it('survives a review with no categories', async () => {
    mockFetch({ ...PROPERTY_PAYLOAD, items: [PROPERTY_PAYLOAD.items[0]] })
    const page = await reviewRepository.forProperty('p1', {})
    expect(page.summary.categoryAverages).toEqual({})
  })
})

describe('mine', () => {
  it('reads a bare array, not a paged envelope', async () => {
    // The endpoint returns `[...]` rather than `{items: [...]}`, because a
    // guest has as many reviews as they have stays. Reading `.items` off an
    // array yields undefined and the page renders empty.
    mockFetch([PROPERTY_PAYLOAD.items[1]])
    const mine = await reviewRepository.mine()

    expect(mine).toHaveLength(1)
    expect(mine[0]?.title).toBe('Quiet mornings by the water')
  })
})

describe('submit', () => {
  it('sends the booking id as the evidence of the stay', async () => {
    let body: Record<string, unknown> = {}
    mockFetch(PROPERTY_PAYLOAD.items[0], (_url, init) => {
      body = bodyOf(init)
    })

    await reviewRepository.submit({
      bookingId: 'b1',
      propertyId: 'p1',
      rating: 5,
      title: 'Lovely',
      body: 'A long enough body to satisfy the server minimum for a review.',
      categories: { cleanliness: 5 },
    })

    expect(body).toMatchObject({ booking_id: 'b1', rating: 5 })
    // The property id is derived from the booking server-side. Sending it
    // would invite a client to claim a review against a different listing.
    expect(body).not.toHaveProperty('property_id')
  })

  it('sends an empty title as null rather than an empty string', async () => {
    let body: Record<string, unknown> = {}
    mockFetch(PROPERTY_PAYLOAD.items[0], (_url, init) => {
      body = bodyOf(init)
    })

    await reviewRepository.submit({
      bookingId: 'b1',
      propertyId: 'p1',
      rating: 5,
      title: '',
      body: 'A long enough body to satisfy the server minimum for a review.',
      categories: {},
    })

    expect(body['title']).toBeNull()
  })
})
