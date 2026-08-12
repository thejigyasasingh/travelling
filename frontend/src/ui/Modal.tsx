/**
 * A dialog built on the native `<dialog>` element.
 *
 * Using the platform element rather than a div-with-a-backdrop buys focus
 * trapping, `Esc` to close, inertness of the page behind, and correct
 * screen-reader semantics — all of which a hand-rolled modal gets wrong, and
 * all of which matter because our modals hold cancellation confirmations.
 */

import { useEffect, useRef, type ReactNode } from 'react'
import { cn } from './cn'

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
}: {
  open: boolean
  onClose: () => void
  title: string
  description?: string
  children?: ReactNode
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg'
}) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    // `close` fires for Esc too, so this is the single place the parent's state
    // gets synced — otherwise Esc closes the dialog and leaves `open === true`,
    // and it can never be reopened.
    const handleClose = () => onClose()
    dialog.addEventListener('close', handleClose)
    return () => dialog.removeEventListener('close', handleClose)
  }, [onClose])

  const widths = { sm: 'max-w-sm', md: 'max-w-lg', lg: 'max-w-2xl' }

  return (
    <dialog
      ref={ref}
      aria-labelledby="modal-title"
      className={cn(
        'w-[calc(100vw-2rem)] rounded-2xl p-0 shadow-lift backdrop:bg-ink-900/40',
        'm-auto open:animate-[fade-in_120ms_ease-out]',
        widths[size],
      )}
      onClick={(event) => {
        // Clicking the backdrop closes. The check is on the target being the
        // dialog itself — clicks inside the content bubble up to here too.
        if (event.target === ref.current) onClose()
      }}
    >
      <div className="p-6">
        <h2 id="modal-title" className="text-lg font-semibold text-ink-900">
          {title}
        </h2>
        {description && <p className="mt-1 text-sm text-ink-500">{description}</p>}
        {children && <div className="mt-4">{children}</div>}
      </div>
      {footer && (
        <div className="flex justify-end gap-2 border-t border-ink-100 bg-ink-50 px-6 py-4">
          {footer}
        </div>
      )}
    </dialog>
  )
}
