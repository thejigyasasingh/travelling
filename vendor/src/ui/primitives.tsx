import type { ReactNode } from 'react'
import { SearchEmptyIcon } from './icons'

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

type Tone = 'neutral' | 'good' | 'warn' | 'bad' | 'brand'

const TONES: Record<Tone, string> = {
  neutral: 'bg-ink-100 text-ink-700 ring-ink-200',
  good: 'bg-good-50 text-good-700 ring-good-200',
  warn: 'bg-warn-50 text-warn-700 ring-warn-200',
  bad: 'bg-bad-50 text-bad-700 ring-bad-200',
  brand: 'bg-brand-50 text-brand-700 ring-brand-200',
}

/** The dot, at full saturation against the tinted pill behind it. */
const DOTS: Record<Tone, string> = {
  neutral: 'bg-ink-400',
  good: 'bg-good-500',
  warn: 'bg-warn-500',
  bad: 'bg-bad-500',
  brand: 'bg-brand-500',
}

export function Badge({
  children,
  tone = 'neutral',
  dot = true,
}: {
  children: ReactNode
  tone?: Tone
  /** Off for a bare count, where a dot beside a number is just clutter. */
  dot?: boolean
}) {
  return (
    <span
      className={cn(
        // `ring` rather than `border`: a 1px ring does not add to the box and
        // therefore cannot shift a table row by a pixel when a status changes.
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs',
        'font-medium whitespace-nowrap capitalize ring-1 ring-inset',
        TONES[tone],
      )}
    >
      {dot && <span className={cn('size-1.5 shrink-0 rounded-full', DOTS[tone])} />}
      {children}
    </span>
  )
}

/**
 * Status colour, in one place.
 *
 * Every table renders a status, and three tables inventing three colour schemes
 * for the same word is how an admin learns to read the text instead of the
 * colour — at which point the colour is just noise.
 */
export function statusTone(status: string): Tone {
  switch (status) {
    case 'confirmed':
    case 'completed':
    case 'captured':
    case 'approved':
    case 'active':
    case 'published':
    case 'sent':
    case 'resolved':
    case 'closed':
      return 'good'
    case 'pending':
    case 'pending_payment':
    case 'pending_approval':
    case 'pending_review':
    case 'under_review':
    case 'queued':
    case 'open':
    case 'in_progress':
    case 'waiting_on_guest':
    case 'authorized':
      return 'warn'
    case 'cancelled':
    case 'expired':
    case 'rejected':
    case 'failed':
    case 'suspended':
    case 'disputed':
    case 'no_show':
      return 'bad'
    case 'in_stay':
      return 'brand'
    default:
      return 'neutral'
  }
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={statusTone(status)}>{status.replace(/_/g, ' ')}</Badge>
}

export function Button({
  children,
  onClick,
  variant = 'secondary',
  size = 'md',
  disabled,
  type = 'button',
  className,
  title,
}: {
  children: ReactNode
  onClick?: () => void
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  disabled?: boolean
  type?: 'button' | 'submit'
  // `| undefined` throughout: under `exactOptionalPropertyTypes` an optional
  // prop still rejects an explicit `undefined`, and a conditional className is
  // exactly what a caller passes.
  className?: string | undefined
  /** A native tooltip. Used where a button's consequence is not obvious from
   *  its label — "take off sale" being the one that matters here. */
  title?: string | undefined
}) {
  const variants = {
    // The shadow is what makes a primary button read as raised rather than
    // painted on. It lifts on hover and settles on press — the whole
    // affordance in two lines.
    primary: 'bg-brand-600 text-white shadow-raised hover:bg-brand-700 hover:shadow-floating',
    secondary: 'bg-white ring-1 ring-ink-200 text-ink-700 shadow-raised hover:bg-ink-50 hover:ring-ink-300',
    ghost: 'text-ink-600 hover:bg-ink-100 hover:text-ink-900',
    danger: 'bg-bad-600 text-white shadow-raised hover:bg-bad-700 hover:shadow-floating',
  }
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        'inline-flex items-center justify-center rounded-lg font-medium',
        'transition-all duration-150 active:translate-y-px active:shadow-none',
        'disabled:opacity-50 disabled:pointer-events-none disabled:shadow-none',
        size === 'sm' ? 'h-8 px-2.5 text-xs gap-1' : 'h-9 px-3 text-sm gap-1.5',
        variants[variant],
        className,
      )}
    >
      {children}
    </button>
  )
}

export function Card({
  children,
  className,
  title,
  description,
  icon,
  action,
}: {
  // Optional so a Card can stand in as a sized skeleton while its content
  // loads, without inventing a second component for the same box.
  children?: ReactNode
  className?: string | undefined
  title?: string | undefined
  /** A sentence under the title. Where a table needs a caveat — "booked
   *  value, not money received" — it belongs here rather than floating
   *  beneath the rows where it is read last or not at all. */
  description?: string | undefined
  icon?: ReactNode
  action?: ReactNode
}) {
  return (
    <section
      className={cn(
        // `ring` not `border`, so the card's box is exactly its content and
        // two cards in a grid line up whatever their state.
        'rounded-xl bg-white ring-1 ring-ink-200/70 shadow-raised',
        className,
      )}
    >
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 border-b border-ink-100 px-4 py-3">
          <div className="flex min-w-0 items-start gap-2.5">
            {icon && (
              <span className="mt-px grid size-7 shrink-0 place-items-center rounded-lg bg-ink-100 text-ink-500">
                {icon}
              </span>
            )}
            <div className="min-w-0">
              {title && (
                <h2 className="truncate text-sm font-semibold text-ink-900">{title}</h2>
              )}
              {description && <p className="mt-0.5 text-xs text-ink-500">{description}</p>}
            </div>
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

export function EmptyRow({
  colSpan,
  message,
  hint,
}: {
  colSpan: number
  message: string
  /** What to do about it. An empty table that only says "nothing here" leaves
   *  a host wondering whether it is empty or broken. */
  hint?: string | undefined
}) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-14">
        <div className="flex flex-col items-center gap-2 text-center">
          <span className="grid size-10 place-items-center rounded-full bg-ink-100 text-ink-400">
            <SearchEmptyIcon className="size-5" />
          </span>
          <p className="text-sm font-medium text-ink-700">{message}</p>
          {hint && <p className="max-w-xs text-xs text-ink-500">{hint}</p>}
        </div>
      </td>
    </tr>
  )
}

/**
 * A block that stands in for content while it loads.
 *
 * A spinner in the middle of a page throws the layout away and rebuilds it,
 * which reads as a jump. A skeleton of roughly the right shape keeps the page
 * still — and on a dashboard where a host is looking for one number, a stable
 * layout is the difference between glancing and re-reading.
 */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('shimmer rounded-md', className)} aria-hidden="true" />
}

/** A page or card with nothing in it yet, outside a table. */
export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon?: ReactNode
  title: string
  hint?: string | undefined
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <span className="grid size-11 place-items-center rounded-full bg-ink-100 text-ink-400">
        {icon ?? <SearchEmptyIcon className="size-5" />}
      </span>
      <div>
        <p className="text-sm font-medium text-ink-800">{title}</p>
        {hint && <p className="mt-1 max-w-sm text-xs text-ink-500">{hint}</p>}
      </div>
      {action}
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cn('size-4 animate-spin', className)} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}
