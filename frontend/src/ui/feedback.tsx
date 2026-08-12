/**
 * Loading, empty and error states.
 *
 * These exist as components because every list needs all three and hand-rolling
 * them per page is how an app ends up with a blank screen for "no results" on
 * one page and a spinner that never resolves on another.
 */

import type { ReactNode } from 'react'
import { isApiError, messageFor } from '@/core/errors'
import { Button } from './Button'
import { cn } from './cn'

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('shimmer rounded-lg', className)} aria-hidden="true" />
}

/** Announced politely so a screen reader says "loading" once, not on every tick. */
export function LoadingBlock({ label = 'Loading' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex flex-col items-center gap-3 py-16">
      <div className="size-8 animate-spin rounded-full border-3 border-ink-200 border-t-brand-600" />
      <p className="text-sm text-ink-500">{label}…</p>
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string
  description?: string
  action?: ReactNode
  icon?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-ink-200 px-6 py-14 text-center">
      {icon && <div className="mb-4 text-ink-300">{icon}</div>}
      <h3 className="text-base font-semibold text-ink-800">{title}</h3>
      {description && <p className="mt-1.5 max-w-sm text-sm text-ink-500">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ErrorState({
  error,
  onRetry,
  title = 'Something went wrong',
}: {
  error: unknown
  onRetry?: () => void
  title?: string
}) {
  const transient = isApiError(error) ? error.isTransient : true
  const requestId = isApiError(error) ? error.requestId : null

  return (
    <div
      role="alert"
      className="rounded-2xl border border-danger-200 bg-danger-50 px-6 py-8 text-center"
    >
      <h3 className="text-base font-semibold text-danger-700">{title}</h3>
      <p className="mt-1.5 text-sm text-ink-600">{messageFor(error)}</p>
      {/* Quoting the request id turns "it broke" into a single log lookup. */}
      {requestId && (
        <p className="mt-2 font-mono text-xs text-ink-400">Reference: {requestId}</p>
      )}
      {onRetry && transient && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

export function InlineError({ error }: { error: unknown }) {
  if (!error) return null
  return (
    <p role="alert" className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">
      {messageFor(error)}
    </p>
  )
}

export function Badge({
  children,
  tone = 'neutral',
  className,
}: {
  children: ReactNode
  tone?: 'neutral' | 'success' | 'pending' | 'danger' | 'active' | 'brand'
  className?: string
}) {
  const tones = {
    neutral: 'bg-ink-100 text-ink-700',
    success: 'bg-success-50 text-success-700',
    pending: 'bg-warning-50 text-warning-700',
    danger: 'bg-danger-50 text-danger-700',
    active: 'bg-brand-100 text-brand-700',
    brand: 'bg-brand-600 text-white',
  }
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
