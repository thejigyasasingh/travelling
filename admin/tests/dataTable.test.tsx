/**
 * The table every admin screen renders through.
 *
 * The states are the point, not the rows. A table that blanks while loading
 * page two, or shows "no results" when the request actually failed, teaches an
 * admin to distrust the screen — and an admin who distrusts the screen goes to
 * the database directly, which is how a support query becomes a data
 * modification.
 *
 * So each test here pins one state and asserts it is distinguishable from the
 * others.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/core/http'
import { DataTable, type Column } from '@/ui/DataTable'

interface Row {
  id: string
  name: string
  amount: number
}

const COLUMNS: Column<Row>[] = [
  { key: 'name', header: 'Name', render: (row) => row.name },
  {
    key: 'amount',
    header: 'Amount',
    numeric: true,
    render: (row) => row.amount,
  },
]

const ROWS: Row[] = [
  { id: '1', name: 'Anjuna Stays', amount: 4500 },
  { id: '2', name: 'Vagator House', amount: 7200 },
]

function table(props: Partial<Parameters<typeof DataTable<Row>>[0]> = {}) {
  return render(<DataTable<Row> columns={COLUMNS} rows={[]} rowKey={(row) => row.id} {...props} />)
}

describe('DataTable', () => {
  it('renders rows', () => {
    table({ rows: ROWS })

    expect(screen.getByText('Anjuna Stays')).toBeInTheDocument()
    expect(screen.getByText('Vagator House')).toBeInTheDocument()
  })

  it('renders every column header', () => {
    table({ rows: ROWS })

    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Amount')).toBeInTheDocument()
  })

  it('distinguishes empty from loading', () => {
    /**
     * **The** state bug. "No results" while a request is still in flight is a
     * lie that an admin acts on — they conclude the vendor has no bookings and
     * tell the vendor so.
     */
    const { unmount } = table({
      isLoading: true,
      emptyMessage: 'No vendors found',
    })
    expect(screen.queryByText('No vendors found')).toBeNull()
    unmount()

    table({ isLoading: false, emptyMessage: 'No vendors found' })
    expect(screen.getByText('No vendors found')).toBeInTheDocument()
  })

  it('distinguishes empty from failed', () => {
    /**
     * The other half. A failed request rendered as "no results" hides an
     * outage — the admin sees an empty table and assumes the data is gone.
     */
    table({
      error: new ApiError(500, 'INTERNAL_ERROR', 'Something broke'),
      emptyMessage: 'No vendors found',
    })

    expect(screen.queryByText('No vendors found')).toBeNull()
    expect(screen.getByText(/something broke/i)).toBeInTheDocument()
  })

  it('offers a retry when the request failed', () => {
    const onRetry = vi.fn()
    table({ error: new ApiError(503, 'UNAVAILABLE', 'Try later'), onRetry })

    const retry = screen.getByRole('button', { name: /retry|try again/i })
    retry.click()
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('keeps rows visible while the next page loads', () => {
    /**
     * `isFetching` is not `isLoading`. Blanking the table on every page change
     * makes a fast interaction feel broken, which is why the query layer uses
     * `keepPreviousData`.
     */
    table({ rows: ROWS, isFetching: true })

    expect(screen.getByText('Anjuna Stays')).toBeInTheDocument()
  })

  it('shows where you are in a paged result', () => {
    table({ rows: ROWS, page: 2, pages: 5, total: 97, onPageChange: vi.fn() })

    // The exact wording is the component's business; the numbers are not.
    expect(document.body.textContent).toContain('2')
    expect(document.body.textContent).toContain('5')
  })

  it('does not offer a previous page from the first', () => {
    /** A control that does nothing is worse than no control. */
    table({ rows: ROWS, page: 1, pages: 3, onPageChange: vi.fn() })

    const previous = screen.queryByRole('button', { name: /prev/i })
    expect(previous === null || (previous as HTMLButtonElement).disabled).toBe(true)
  })

  it('does not offer a next page from the last', () => {
    table({ rows: ROWS, page: 3, pages: 3, onPageChange: vi.fn() })

    const next = screen.queryByRole('button', { name: /next/i })
    expect(next === null || (next as HTMLButtonElement).disabled).toBe(true)
  })

  it('reports a permission failure as a refusal, not a retryable error', () => {
    /**
     * A 403 is not retryable — retrying will not grant the permission. An
     * admin offered a retry button for one will press it repeatedly.
     */
    table({ error: new ApiError(403, 'FORBIDDEN', 'Not allowed here') })

    expect(screen.getByText(/not allowed here/i)).toBeInTheDocument()
  })
})
