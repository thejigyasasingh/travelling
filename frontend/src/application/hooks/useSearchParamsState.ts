/**
 * Search filters live in the **URL**, not in component state.
 *
 * This is the decision that makes search behave the way people expect: a
 * filtered result set can be shared, bookmarked, and reloaded; the back button
 * undoes a filter instead of leaving the page; and the server-rendered link a
 * guest sends a friend shows the same stays at the same prices.
 *
 * It also removes a whole class of bug. With one source of truth there is no
 * state to keep in sync with the query string, so the two cannot disagree.
 */

import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { CriteriaPatch, SearchCriteria, SortOption } from '@/application/ports'
import type { IsoDate } from '@/core/dates'
import { isIsoDate } from '@/core/dates'

const SORTS: readonly SortOption[] = [
  'relevance',
  'price_asc',
  'price_desc',
  'rating_desc',
  'distance_asc',
  'newest',
]

function num(value: string | null): number | undefined {
  if (value === null || value.trim() === '') return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

function date(value: string | null): IsoDate | undefined {
  return value !== null && isIsoDate(value) ? value : undefined
}

/** Parse the query string into criteria. Junk is dropped, never crashed on. */
export function criteriaFromParams(params: URLSearchParams): SearchCriteria {
  const sortParam = params.get('sort')
  const criteria: Record<string, unknown> = {
    q: params.get('q') ?? undefined,
    cityId: params.get('city') ?? undefined,
    lat: num(params.get('lat')),
    lng: num(params.get('lng')),
    radiusM: num(params.get('radius')),
    checkIn: date(params.get('check_in')),
    checkOut: date(params.get('check_out')),
    adults: num(params.get('adults')),
    children: num(params.get('children')),
    infants: num(params.get('infants')),
    rooms: num(params.get('rooms')),
    propertyType: params.getAll('type'),
    amenity: params.getAll('amenity'),
    minPrice: num(params.get('min_price')),
    maxPrice: num(params.get('max_price')),
    minRating: num(params.get('min_rating')),
    instantBooking: params.get('instant') === '1' ? true : undefined,
    cancellation: params.get('cancellation') ?? undefined,
    sort: SORTS.includes(sortParam as SortOption) ? (sortParam) : undefined,
  }
  for (const [key, value] of Object.entries(criteria)) {
    if (value === undefined || (Array.isArray(value) && value.length === 0)) delete criteria[key]
  }
  return criteria
}

export function paramsFromCriteria(criteria: CriteriaPatch): URLSearchParams {
  const params = new URLSearchParams()
  const put = (key: string, value: string | number | boolean | readonly string[] | undefined) => {
    if (value === undefined || value === '') return
    if (Array.isArray(value)) (value as readonly string[]).forEach((v) => params.append(key, v))
    else params.set(key, String(value))
  }
  put('q', criteria.q)
  put('city', criteria.cityId)
  put('lat', criteria.lat)
  put('lng', criteria.lng)
  put('radius', criteria.radiusM)
  put('check_in', criteria.checkIn)
  put('check_out', criteria.checkOut)
  put('adults', criteria.adults)
  put('children', criteria.children)
  put('infants', criteria.infants)
  put('rooms', criteria.rooms)
  put('type', criteria.propertyType)
  put('amenity', criteria.amenity)
  put('min_price', criteria.minPrice)
  put('max_price', criteria.maxPrice)
  put('min_rating', criteria.minRating)
  if (criteria.instantBooking) params.set('instant', '1')
  put('cancellation', criteria.cancellation)
  put('sort', criteria.sort)
  return params
}

export function useSearchCriteria() {
  const [params, setParams] = useSearchParams()
  const criteria = useMemo(() => criteriaFromParams(params), [params])

  const update = useCallback(
    (patch: CriteriaPatch, options: { replace?: boolean } = {}) => {
      const next = { ...criteria, ...patch }
      // Any filter change invalidates the cursor: page 3 of the old result set
      // is meaningless in the new one.
      delete (next as { cursor?: string }).cursor
      setParams(paramsFromCriteria(next), { replace: options.replace ?? false })
    },
    [criteria, setParams],
  )

  const toggleInArray = useCallback(
    (key: 'propertyType' | 'amenity', value: string) => {
      const current = criteria[key] ?? []
      const next = current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value]
      update({ [key]: next })
    },
    [criteria, update],
  )

  const reset = useCallback(() => {
    // Dates and guests survive a filter reset: they describe the trip, not the
    // filtering of it, and clearing them is never what "clear filters" means.
    const kept: SearchCriteria = {}
    const carry = ['q', 'cityId', 'checkIn', 'checkOut', 'adults', 'children', 'infants', 'rooms'] as const
    for (const key of carry) {
      const value = criteria[key]
      if (value !== undefined) (kept as Record<string, unknown>)[key] = value
    }
    setParams(paramsFromCriteria(kept))
  }, [criteria, setParams])

  const activeFilterCount = useMemo(() => {
    let n = 0
    if (criteria.propertyType?.length) n += criteria.propertyType.length
    if (criteria.amenity?.length) n += criteria.amenity.length
    if (criteria.minPrice !== undefined || criteria.maxPrice !== undefined) n += 1
    if (criteria.minRating !== undefined) n += 1
    if (criteria.instantBooking) n += 1
    if (criteria.cancellation) n += 1
    return n
  }, [criteria])

  return { criteria, update, toggleInArray, reset, activeFilterCount }
}
