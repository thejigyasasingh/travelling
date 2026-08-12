// Load profile for the two endpoints that decide whether the site stays up.
//
// Run it with k6:
//
//   k6 run -e BASE_URL=https://staging.roamingwandering.com deploy/load/search.js
//
// **Why these two.** `GET /search` is the heaviest read in the platform — a
// scoring query with a PostGIS distance term and a lateral join per row — and
// it is the one endpoint anonymous traffic can hit without limit. `POST /quote`
// is the heaviest *write-path* read: it prices a stay across a date range and
// runs immediately before every booking. If either falls over, nobody books.
//
// **What this is actually for.** The connection pool is 10 with 5 overflow, the
// anonymous search limit is 60/minute, and worker concurrency is 4. Every one
// of those numbers was chosen by judgement and none has been measured. This
// script exists to replace three guesses with three observations — run it,
// watch `ConnectionPoolNearlyFull` and p95 latency, and move the numbers that
// turn out to be wrong.
//
// Not run in CI. A load test on a shared runner measures the runner, and a
// threshold that fails for that reason gets deleted within a month. Run it
// against staging, deliberately, when something about the shape of traffic
// changes.

import http from 'k6/http'
import { check, group, sleep } from 'k6'
import { Rate, Trend } from 'k6/metrics'

const BASE = __ENV.BASE_URL || 'http://localhost:8000'

// Tracked separately from the built-in aggregate: search and quote have very
// different acceptable latencies, and one average over both hides whichever is
// slower.
const searchLatency = new Trend('search_duration', true)
const quoteLatency = new Trend('quote_duration', true)
const throttled = new Rate('throttled')

export const options = {
  scenarios: {
    // A slow ramp rather than a step. A step to full load measures cold caches
    // and an empty connection pool, which is a real scenario but not this one
    // — this is "a busy evening", and the interesting failures appear as
    // pressure builds.
    browse: {
      executor: 'ramping-vus',
      exec: 'browse',
      startVUs: 1,
      stages: [
        { duration: '1m', target: 20 },
        { duration: '3m', target: 20 },
        { duration: '1m', target: 60 },
        { duration: '3m', target: 60 },
        { duration: '1m', target: 0 },
      ],
    },
    // Quotes are a fraction of searches in real traffic: people look at many
    // listings and price a few. A 1:10 ratio keeps the mix honest.
    price: {
      executor: 'ramping-vus',
      exec: 'price',
      startVUs: 1,
      stages: [
        { duration: '1m', target: 2 },
        { duration: '3m', target: 2 },
        { duration: '1m', target: 6 },
        { duration: '3m', target: 6 },
        { duration: '1m', target: 0 },
      ],
    },
  },
  thresholds: {
    // Targets, not guarantees — the first run is what tells you whether they
    // are the right ones. Set from what a person notices: a search that takes
    // over a second feels broken, a quote over two seconds makes people press
    // the button again.
    search_duration: ['p(95)<1000'],
    quote_duration: ['p(95)<2000'],
    // A 5xx under load is the finding. Anything above a rounding error means
    // stop and look rather than tune.
    http_req_failed: ['rate<0.01'],
  },
}

const CITIES = ['Anjuna', 'Vagator', 'Assagao', 'Morjim', 'Arambol']
const SORTS = ['relevance', 'price_asc', 'rating_desc']

function pick(list) {
  return list[Math.floor(Math.random() * list.length)]
}

/** A stay a few weeks out, so the search is not always for the same dates. */
function stay() {
  const start = new Date()
  start.setDate(start.getDate() + 14 + Math.floor(Math.random() * 60))
  const end = new Date(start)
  end.setDate(end.getDate() + 1 + Math.floor(Math.random() * 5))
  const iso = (d) => d.toISOString().slice(0, 10)
  return { checkIn: iso(start), checkOut: iso(end) }
}

function record(response, trend) {
  trend.add(response.timings.duration)
  // A 429 is the rate limiter doing its job, not a failure — but if the whole
  // run is throttled the latency numbers mean nothing, so it is measured
  // rather than ignored.
  throttled.add(response.status === 429)
  return response
}

export function browse() {
  group('search', () => {
    const { checkIn, checkOut } = stay()
    const url =
      `${BASE}/api/v1/search?q=${pick(CITIES)}` +
      `&check_in=${checkIn}&check_out=${checkOut}` +
      `&adults=2&sort=${pick(SORTS)}&limit=20`

    const response = record(http.get(url, { tags: { name: 'search' } }), searchLatency)
    check(response, {
      'search answered': (r) => r.status === 200 || r.status === 429,
      'search returned a page': (r) => r.status !== 200 || r.json('items') !== undefined,
    })

    // Page two, for a third of them. Keyset pagination is a different query
    // plan from page one and it is the one that regressed last time.
    if (response.status === 200 && Math.random() < 0.33) {
      const cursor = response.json('next_cursor')
      if (cursor) {
        record(
          http.get(`${url}&cursor=${encodeURIComponent(cursor)}`, { tags: { name: 'search_page2' } }),
          searchLatency,
        )
      }
    }
  })

  // Think time. Back-to-back requests measure a benchmark, not a person.
  sleep(1 + Math.random() * 3)
}

export function price() {
  group('quote', () => {
    const { checkIn, checkOut } = stay()
    const found = http.get(`${BASE}/api/v1/search?q=${pick(CITIES)}&adults=2&limit=5`)
    if (found.status !== 200) return

    const items = found.json('items') || []
    if (items.length === 0) return
    const property = items[Math.floor(Math.random() * items.length)]

    const detail = http.get(`${BASE}/api/v1/properties/${property.slug}`)
    if (detail.status !== 200) return
    const rooms = detail.json('room_types') || []
    if (rooms.length === 0) return

    const response = record(
      http.post(
        `${BASE}/api/v1/properties/${property.id}/quote`,
        JSON.stringify({
          room_type_id: rooms[0].id,
          check_in: checkIn,
          check_out: checkOut,
          adults: 2,
          children: 0,
          infants: 0,
          rooms: 1,
        }),
        { headers: { 'Content-Type': 'application/json' }, tags: { name: 'quote' } },
      ),
      quoteLatency,
    )

    check(response, {
      'quote answered': (r) => [200, 409, 422, 429].includes(r.status),
    })
  })

  sleep(2 + Math.random() * 4)
}

export function handleSummary(data) {
  // Printed rather than uploaded. The numbers worth keeping go in the
  // deployment README next to the pool settings they justify.
  const p95 = (metric) => Math.round(data.metrics[metric]?.values?.['p(95)'] ?? 0)
  return {
    stdout:
      '\n' +
      `search p95   ${p95('search_duration')} ms\n` +
      `quote  p95   ${p95('quote_duration')} ms\n` +
      `throttled    ${((data.metrics.throttled?.values?.rate ?? 0) * 100).toFixed(1)}%\n` +
      `failed       ${((data.metrics.http_req_failed?.values?.rate ?? 0) * 100).toFixed(2)}%\n\n` +
      'Watch alongside: ConnectionPoolNearlyFull, SlowRequests, and\n' +
      'pg_stat_activity — the pool is the first thing to saturate.\n',
  }
}
