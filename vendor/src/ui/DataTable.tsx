import type { ReactNode } from 'react'
import { ApiError } from '@/core/http'
import { Button, EmptyRow, Skeleton, Spinner, cn } from './primitives'
import { AlertIcon } from './icons'

/** Cycled so adjacent skeleton cells differ. */
const SKELETON_WIDTHS = ['w-4/5', 'w-3/5', 'w-full', 'w-2/3', 'w-1/2'] as const

export interface Column<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
  /** Right-aligned and tabular. Numbers that do not line up cannot be compared
   *  down a column, which is the only reason they are in a column. */
  numeric?: boolean
  className?: string
}

/**
 * The table every admin screen uses.
 *
 * One implementation rather than ten, because the states are what people
 * actually notice: a table that blanks while loading page two, or shows "no
 * results" when the request failed, teaches an admin to distrust the screen.
 *
 * Paging is offset-based. An admin list is a bounded internal set someone pages
 * through by number and sorts by column; cursor paging would make "page 4"
 * unexpressible for no benefit at this scale.
 */
export function DataTable<T>({
  columns,
  rows,
  isLoading,
  isFetching,
  error,
  onRetry,
  emptyMessage = 'Nothing to show',
  page,
  pages,
  total,
  onPageChange,
  rowKey,
  onRowClick,
}: {
  columns: Column<T>[]
  rows: T[]
  isLoading?: boolean | undefined
  isFetching?: boolean | undefined
  error?: unknown
  onRetry?: (() => void) | undefined
  emptyMessage?: string | undefined
  page?: number | undefined
  pages?: number | undefined
  total?: number | undefined
  onPageChange?: ((page: number) => void) | undefined
  rowKey: (row: T) => string
  onRowClick?: ((row: T) => void) | undefined
}) {
  const apiError = error instanceof ApiError ? error : null

  return (
    <div className="overflow-hidden rounded-xl bg-white shadow-raised ring-1 ring-ink-200/70">
      {/* `max-h` plus a sticky header: a hundred-row page keeps its column
          labels while it scrolls, which is the difference between reading a
          table and counting columns back to the top. */}
      <div className="max-h-[70vh] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 border-b border-ink-100 bg-ink-50/95 backdrop-blur-sm">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className={cn(
                    'px-4 py-2.5 text-xs font-semibold text-ink-500 uppercase tracking-wide',
                    column.numeric ? 'text-right' : 'text-left',
                  )}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {isLoading ? (
              Array.from({ length: 6 }, (_, i) => (
                <tr key={i}>
                  {columns.map((column, c) => (
                    <td key={column.key} className="px-4 py-3">
                      {/* Varying widths, so the block reads as loading text
                          rather than as a rendered grid of empty cells. */}
                      <Skeleton
                        className={cn('h-3', SKELETON_WIDTHS[(i + c) % SKELETON_WIDTHS.length])}
                      />
                    </td>
                  ))}
                </tr>
              ))
            ) : error ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-14 text-center">
                  <span
                    className={cn(
                      'mx-auto mb-3 grid size-10 place-items-center rounded-full',
                      apiError?.isForbidden ? 'bg-ink-100 text-ink-400' : 'bg-bad-50 text-bad-500',
                    )}
                  >
                    <AlertIcon className="size-5" />
                  </span>
                  <p className="text-sm font-medium text-bad-700">
                    {apiError?.isForbidden
                      ? 'You do not have permission to see this'
                      : 'Could not load this list'}
                  </p>
                  <p className="mt-1 text-sm text-ink-500">
                    {apiError?.message ?? 'Something went wrong.'}
                  </p>
                  {apiError?.requestId && (
                    <p className="mt-1 font-mono text-xs text-ink-400">
                      Reference: {apiError.requestId}
                    </p>
                  )}
                  {/* No retry for a permission failure — retrying will not grant
                      it, and the button would teach people that buttons lie. */}
                  {onRetry && apiError?.isRetryable !== false && !apiError?.isForbidden && (
                    <Button size="sm" className="mt-3" onClick={onRetry}>
                      Try again
                    </Button>
                  )}
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <EmptyRow colSpan={columns.length} message={emptyMessage} />
            ) : (
              rows.map((row) => (
                <tr
                  key={rowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={cn(
                    'transition-colors',
                    onRowClick
                      ? 'cursor-pointer hover:bg-brand-50/60'
                      : 'hover:bg-ink-50/70',
                  )}
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn(
                        'px-4 py-2.5 text-ink-700',
                        column.numeric && 'text-right tabular',
                        column.className,
                      )}
                    >
                      {column.render(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {(pages ?? 0) > 0 && (
        <footer className="flex items-center justify-between border-t border-ink-100 px-4 py-2.5">
          <p className="flex items-center gap-2 text-xs text-ink-500">
            {/* Shown while a page loads, next to the count rather than over the
                table — so the rows stay readable during the fetch. */}
            {isFetching && <Spinner className="size-3" />}
            {total !== undefined && <span>{total.toLocaleString('en-IN')} total</span>}
          </p>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              disabled={(page ?? 1) <= 1}
              onClick={() => onPageChange?.((page ?? 1) - 1)}
            >
              Previous
            </Button>
            <span className="text-xs text-ink-500">
              Page {page ?? 1} of {pages ?? 1}
            </span>
            <Button
              size="sm"
              disabled={(page ?? 1) >= (pages ?? 1)}
              onClick={() => onPageChange?.((page ?? 1) + 1)}
            >
              Next
            </Button>
          </div>
        </footer>
      )}
    </div>
  )
}

/** A search box that writes to the URL, so a filtered admin view is a link
 *  someone can paste into a ticket. */
export function FilterBar({ children }: { children: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2">{children}</div>
  )
}

export function SearchInput({
  value,
  onChange,
  placeholder = 'Search…',
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}) {
  return (
    <input
      type="search"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
      className="h-9 w-60 rounded-lg border border-ink-200 bg-white px-3 text-sm placeholder:text-ink-400 focus:border-brand-500"
    />
  )
}

export function Select({
  value,
  onChange,
  options,
  label,
}: {
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  label: string
}) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-ink-500">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 rounded-lg border border-ink-200 bg-white px-2 text-sm text-ink-700"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}
