import type { ReactNode } from 'react'

export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

type Tone = 'neutral' | 'good' | 'warn' | 'bad' | 'brand'

const TONES: Record<Tone, string> = {
  neutral: 'bg-ink-100 text-ink-700',
  good: 'bg-good-50 text-good-700',
  warn: 'bg-warn-50 text-warn-700',
  bad: 'bg-bad-50 text-bad-700',
  brand: 'bg-brand-100 text-brand-700',
}

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: Tone
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        TONES[tone],
      )}
    >
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
    primary: 'bg-brand-600 text-white hover:bg-brand-700',
    secondary: 'bg-white border border-ink-200 text-ink-700 hover:bg-ink-50',
    ghost: 'text-ink-600 hover:bg-ink-100',
    danger: 'bg-bad-600 text-white hover:bg-bad-700',
  }
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        'inline-flex items-center justify-center rounded-lg font-medium transition-colors',
        'disabled:opacity-50 disabled:pointer-events-none',
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
  action,
}: {
  // Optional so a Card can stand in as a sized skeleton while its content
  // loads, without inventing a second component for the same box.
  children?: ReactNode
  className?: string | undefined
  title?: string | undefined
  action?: ReactNode
}) {
  return (
    <section className={cn('rounded-xl border border-ink-200 bg-white', className)}>
      {(title || action) && (
        <header className="flex items-center justify-between border-b border-ink-100 px-4 py-3">
          {title && <h2 className="text-sm font-semibold text-ink-800">{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  )
}

export function EmptyRow({ colSpan, message }: { colSpan: number; message: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-4 py-12 text-center text-sm text-ink-500">
        {message}
      </td>
    </tr>
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
