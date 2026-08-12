import { useEffect, useState } from 'react'
import { formatCountdown } from '@/core/dates'
import { cn } from '@/ui/cn'

/**
 * The hold countdown.
 *
 * Not decoration: when it reaches zero the rooms genuinely go back on sale and
 * the booking expires. Showing it is the difference between a guest who knows
 * they have twelve minutes and one who wanders off and loses the room.
 *
 * It counts down from a *duration* the server sent, not to a client timestamp —
 * a device with a wrong clock would otherwise show a nonsense number.
 */
export function HoldCountdown({
  seconds,
  onExpire,
}: {
  seconds: number
  onExpire?: () => void
}) {
  const [remaining, setRemaining] = useState(seconds)

  useEffect(() => {
    // The clock is read only inside the effect. Reading `Date.now()` during
    // render makes the component impure — two renders with the same props
    // would produce different output, which breaks under concurrent rendering.
    const deadline = Date.now() + seconds * 1000

    // Recomputed from the deadline each tick rather than decremented by one: a
    // backgrounded tab throttles timers, and a counter that only subtracts
    // would come back minutes behind the real hold.
    const timer = setInterval(() => {
      setRemaining(Math.max(0, Math.round((deadline - Date.now()) / 1000)))
    }, 1000)
    return () => clearInterval(timer)
  }, [seconds])

  useEffect(() => {
    if (remaining <= 0) onExpire?.()
  }, [remaining, onExpire])

  const urgent = remaining <= 120

  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-xl px-3 py-2 text-sm',
        urgent ? 'bg-danger-50 text-danger-700' : 'bg-warning-50 text-warning-700',
      )}
      // `polite`, not `assertive`: a per-second assertive region would make a
      // screen reader interrupt itself every tick and the page unusable.
      role="status"
      aria-live="polite"
    >
      <ClockIcon />
      {remaining > 0 ? (
        <span>
          Your rooms are held for{' '}
          <strong className="tabular-nums">{formatCountdown(remaining)}</strong>
        </span>
      ) : (
        <span>This hold has expired. The rooms have been released.</span>
      )}
    </div>
  )
}

function ClockIcon() {
  return (
    <svg className="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" strokeLinecap="round" />
    </svg>
  )
}
