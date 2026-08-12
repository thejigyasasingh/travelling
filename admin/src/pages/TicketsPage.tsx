import { useState } from 'react'
import {
  useReplyToTicket,
  useResolveTicket,
  useSetTicketPriority,
  useTicketCounts,
  useTickets,
} from '@/api/queries'
import { useListFilters } from '@/app/useListFilters'
import { PageHeader } from '@/app/Shell'
import { FilterBar, SearchInput, Select } from '@/ui/DataTable'
import { Badge, Button, Card, StatusBadge, cn } from '@/ui/primitives'
import { formatDateTime, formatRelative } from '@/core/format'
import { ApiError } from '@/core/http'
import type { Ticket } from '@/api/types'

const PRIORITY_TONE = {
  urgent: 'bad',
  high: 'warn',
  normal: 'neutral',
  low: 'neutral',
} as const

/**
 * The support queue.
 *
 * A list-and-detail rather than a table: an agent works one conversation at a
 * time, and a table of subjects makes you click into each to find out what it
 * is about.
 *
 * The queue is ordered by priority then age, server-side — an urgent ticket
 * from five minutes ago outranks a low one from yesterday, which is the reverse
 * of what a reverse-chronological list would show.
 */
export function TicketsPage() {
  const { filters, update } = useListFilters({ status: 'open' })
  const query = useTickets(filters)
  const counts = useTicketCounts()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const tickets = query.data?.items ?? []
  const selected = tickets.find((t) => t.id === selectedId) ?? tickets[0] ?? null

  return (
    <>
      <PageHeader
        title="Support"
        description="Ordered by priority, then age — the ticket most at risk first"
      />

      <FilterBar>
        <SearchInput
          value={String(filters.q ?? '')}
          onChange={(q) => update({ q })}
          placeholder="Reference, subject or email"
        />
        <Select
          label="Status"
          value={String(filters.status ?? 'open')}
          onChange={(status) => update({ status })}
          options={[
            { value: 'open', label: 'Open' },
            { value: '', label: 'All' },
            { value: 'in_progress', label: 'In progress' },
            { value: 'waiting_on_guest', label: 'Waiting on guest' },
            { value: 'resolved', label: 'Resolved' },
            { value: 'closed', label: 'Closed' },
          ]}
        />
        <Select
          label="Priority"
          value={String(filters.priority ?? '')}
          onChange={(priority) => update({ priority })}
          options={[
            { value: '', label: 'Any' },
            { value: 'urgent', label: 'Urgent' },
            { value: 'high', label: 'High' },
            { value: 'normal', label: 'Normal' },
            { value: 'low', label: 'Low' },
          ]}
        />
        {counts.data && (
          <span className="ml-auto flex gap-1.5 text-xs">
            {Object.entries(counts.data.counts).map(([status, count]) => (
              <Badge key={status}>
                {status.replace(/_/g, ' ')} {count}
              </Badge>
            ))}
          </span>
        )}
      </FilterBar>

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card className="overflow-hidden">
          {query.isPending ? (
            <p className="p-4 text-sm text-ink-500">Loading…</p>
          ) : query.error ? (
            <p className="p-4 text-sm text-bad-700">
              {query.error instanceof ApiError && query.error.isForbidden
                ? 'You do not have permission to see the queue.'
                : 'Could not load the queue.'}
            </p>
          ) : tickets.length === 0 ? (
            <p className="p-6 text-center text-sm text-ink-500">Nothing in this queue</p>
          ) : (
            <ul className="max-h-[70vh] divide-y divide-ink-100 overflow-y-auto">
              {tickets.map((ticket) => (
                <li key={ticket.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(ticket.id)}
                    className={cn(
                      'w-full px-3 py-2.5 text-left hover:bg-ink-50',
                      selected?.id === ticket.id && 'bg-brand-50',
                    )}
                  >
                    <div className="flex items-center gap-1.5">
                      <Badge tone={PRIORITY_TONE[ticket.priority as keyof typeof PRIORITY_TONE]}>
                        {ticket.priority}
                      </Badge>
                      {/* The one thing an agent must see before choosing: this
                          ticket has had no reply and its target has passed. */}
                      {ticket.is_breaching && <Badge tone="bad">late</Badge>}
                      <span className="ml-auto font-mono text-[11px] text-ink-400">
                        {ticket.reference}
                      </span>
                    </div>
                    <p className="mt-1 truncate text-sm font-medium text-ink-800">
                      {ticket.subject}
                    </p>
                    <p className="truncate text-xs text-ink-500">
                      {ticket.requester_email} · {formatRelative(ticket.opened_at)}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {selected ? <TicketDetail ticket={selected} /> : <Card className="p-6 text-sm text-ink-500">Select a ticket</Card>}
      </div>
    </>
  )
}

function TicketDetail({ ticket }: { ticket: Ticket }) {
  const reply = useReplyToTicket()
  const resolve = useResolveTicket()
  const setPriority = useSetTicketPriority()

  const [body, setBody] = useState('')
  const [internal, setInternal] = useState(false)
  const [resolution, setResolution] = useState('')

  return (
    <Card>
      <header className="border-b border-ink-100 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-ink-900">{ticket.subject}</h2>
            <p className="text-xs text-ink-500">
              <span className="font-mono">{ticket.reference}</span> · {ticket.requester_name} ·{' '}
              {ticket.requester_email}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <StatusBadge status={ticket.status} />
            <select
              value={ticket.priority}
              onChange={(event) =>
                setPriority.mutate({ id: ticket.id, priority: event.target.value })
              }
              className="h-7 rounded-lg border border-ink-200 px-1.5 text-xs"
              aria-label="Priority"
            >
              {['urgent', 'high', 'normal', 'low'].map((priority) => (
                <option key={priority} value={priority}>
                  {priority}
                </option>
              ))}
            </select>
          </div>
        </div>
        <p className="mt-2 text-xs text-ink-500">
          Opened {formatDateTime(ticket.opened_at)} · first reply due{' '}
          {formatDateTime(ticket.response_due_at)}
          {ticket.first_responded_at
            ? ` · answered ${formatRelative(ticket.first_responded_at)}`
            : ticket.is_breaching
              ? ' · overdue'
              : ''}
        </p>
      </header>

      <div className="max-h-[45vh] space-y-3 overflow-y-auto p-4">
        {ticket.messages.map((message) => (
          <article
            key={message.id}
            className={cn(
              'rounded-lg p-3 text-sm',
              message.is_internal
                ? // Visually unmistakable. An agent must never mistake an
                  // internal note for something the guest can see.
                  'border border-dashed border-warn-600/40 bg-warn-50'
                : 'bg-ink-50',
            )}
          >
            <p className="flex items-center gap-2 text-xs text-ink-500">
              <span className="font-medium text-ink-700">{message.author_name}</span>
              {message.is_internal && <Badge tone="warn">internal — not sent to guest</Badge>}
              <span className="ml-auto">{formatDateTime(message.sent_at)}</span>
            </p>
            <p className="mt-1.5 whitespace-pre-line text-ink-800">{message.body}</p>
          </article>
        ))}
      </div>

      {ticket.status !== 'closed' && (
        <div className="space-y-3 border-t border-ink-100 p-4">
          {(reply.error ?? resolve.error) && (
            <p role="alert" className="rounded-lg bg-bad-50 p-2 text-xs text-bad-700">
              {(reply.error ?? resolve.error) instanceof ApiError
                ? (reply.error ?? resolve.error)!.message
                : 'That action failed.'}
            </p>
          )}

          <textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            rows={3}
            placeholder="Reply to the guest…"
            className={cn(
              'w-full rounded-lg border px-3 py-2 text-sm',
              internal ? 'border-warn-600/50 bg-warn-50' : 'border-ink-200',
            )}
          />
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-ink-700">
              <input
                type="checkbox"
                checked={internal}
                onChange={(event) => setInternal(event.target.checked)}
              />
              Internal note
            </label>
            <Button
              variant="primary"
              size="sm"
              disabled={reply.isPending || body.trim().length === 0}
              onClick={() =>
                reply.mutate(
                  { id: ticket.id, body, internal },
                  { onSuccess: () => setBody('') },
                )
              }
            >
              {internal ? 'Add note' : 'Send reply'}
            </Button>
            {internal && (
              <span className="text-xs text-warn-700">
                This will not be sent to the guest and they cannot see it.
              </span>
            )}
          </div>

          {ticket.status !== 'resolved' && (
            <div className="flex flex-wrap items-center gap-2 border-t border-ink-100 pt-3">
              <input
                value={resolution}
                onChange={(event) => setResolution(event.target.value)}
                placeholder="What was done? (required to resolve)"
                className="h-9 min-w-64 flex-1 rounded-lg border border-ink-200 px-2 text-sm"
              />
              <Button
                size="sm"
                disabled={resolve.isPending || resolution.trim().length < 3}
                onClick={() =>
                  resolve.mutate(
                    { id: ticket.id, resolution },
                    { onSuccess: () => setResolution('') },
                  )
                }
              >
                Resolve
              </Button>
            </div>
          )}
        </div>
      )}

      {ticket.resolution && (
        <p className="border-t border-ink-100 bg-good-50 p-3 text-xs text-good-700">
          Resolved: {ticket.resolution}
        </p>
      )}
    </Card>
  )
}
