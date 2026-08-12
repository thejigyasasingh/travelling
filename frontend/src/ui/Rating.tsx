import { ratingLabel } from '@/domain/review'
import { cn } from './cn'

/**
 * A rating.
 *
 * `0 reviews` renders as "New" rather than as zero stars: a new listing showing
 * an empty five-star row reads as "rated 0/5", which is both wrong and unfair
 * to the host.
 */
export function Rating({
  value,
  count,
  size = 'sm',
  showLabel = false,
  className,
}: {
  value: number
  count?: number
  size?: 'sm' | 'md'
  showLabel?: boolean
  className?: string
}) {
  const isNew = !count || count === 0

  return (
    <span
      className={cn('inline-flex items-center gap-1', size === 'sm' ? 'text-sm' : 'text-base', className)}
      // One label for the whole control; the pieces below are decorative.
      aria-label={isNew ? 'No reviews yet' : `Rated ${value.toFixed(1)} out of 5 from ${count} reviews`}
    >
      <StarIcon className={cn(size === 'sm' ? 'size-4' : 'size-5', isNew ? 'text-ink-300' : 'text-brand-600')} />
      {isNew ? (
        <span className="text-ink-500">New</span>
      ) : (
        <>
          <span className="font-semibold text-ink-800">{value.toFixed(1)}</span>
          {showLabel && <span className="text-ink-500">{ratingLabel(value)}</span>}
          {count !== undefined && (
            <span className="text-ink-500">
              ({count.toLocaleString('en-IN')})
            </span>
          )}
        </>
      )}
    </span>
  )
}

export function StarIcon({ className, filled = true }: { className?: string; filled?: boolean }) {
  return (
    <svg
      className={className}
      viewBox="0 0 20 20"
      fill={filled ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth={filled ? 0 : 1.5}
      aria-hidden="true"
    >
      <path d="M10 1.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8L1.5 7.7l5.9-.9L10 1.5z" />
    </svg>
  )
}

/** The interactive version, for writing a review. Keyboard-operable. */
export function StarInput({
  value,
  onChange,
  label = 'Rating',
}: {
  value: number
  onChange: (value: number) => void
  label?: string
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          role="radio"
          aria-checked={value === star}
          aria-label={`${star} star${star === 1 ? '' : 's'}`}
          onClick={() => onChange(star)}
          className="rounded p-1 transition-transform hover:scale-110"
        >
          <StarIcon
            className={cn('size-7', star <= value ? 'text-brand-600' : 'text-ink-200')}
          />
        </button>
      ))}
    </div>
  )
}
