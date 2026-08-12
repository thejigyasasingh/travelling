import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { ListFilters } from '@/api/queries'

/**
 * List filters, held in the URL.
 *
 * The reason is specific to an admin tool: support and engineering paste these
 * links to each other. "The failed payments are here" has to be a URL, not a
 * sequence of clicks to reproduce.
 */
export function useListFilters(defaults: ListFilters = {}) {
  const [params, setParams] = useSearchParams()

  const filters = useMemo<ListFilters>(() => {
    const result: ListFilters = { page: 1, size: 20, ...defaults }
    for (const [key, value] of params.entries()) {
      result[key] = key === 'page' || key === 'size' ? Number(value) : value
    }
    return result
  }, [params, defaults])

  const update = useCallback(
    (patch: ListFilters) => {
      const next = new URLSearchParams(params)
      for (const [key, value] of Object.entries(patch)) {
        if (value === undefined || value === '' || value === null) next.delete(key)
        else next.set(key, String(value))
      }
      // Any filter change resets to page one: page 4 of the previous result set
      // is meaningless in the new one, and landing on an empty page reads as
      // "no results".
      if (!('page' in patch)) next.delete('page')
      setParams(next, { replace: true })
    },
    [params, setParams],
  )

  return { filters, update }
}
