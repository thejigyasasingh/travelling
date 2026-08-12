/**
 * Form primitives.
 *
 * Every input is wired to its label and, when invalid, to its error message via
 * `aria-describedby` + `aria-invalid`. A red border alone communicates nothing
 * to a screen reader and nothing to the ~8% of men with a colour vision
 * deficiency, so the message is always text as well.
 */

import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { cn } from './cn'

const CONTROL =
  'w-full rounded-xl border bg-white px-3 py-2.5 text-sm text-ink-900 placeholder:text-ink-400 ' +
  'transition-colors focus:border-brand-500 disabled:bg-ink-50 disabled:text-ink-500'

interface FieldShellProps {
  label: string
  error?: string | undefined
  hint?: string | undefined
  required?: boolean
  children: (props: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode
  className?: string
}

export function Field({ label, error, hint, required, children, className }: FieldShellProps) {
  const id = useId()
  const errorId = `${id}-error`
  const hintId = `${id}-hint`
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(' ') || undefined

  return (
    <div className={cn('space-y-1.5', className)}>
      <label htmlFor={id} className="block text-sm font-medium text-ink-700">
        {label}
        {required && (
          <span className="text-danger-600" aria-hidden="true">
            {' '}
            *
          </span>
        )}
      </label>
      {children({ id, describedBy, invalid: Boolean(error) })}
      {hint && !error && (
        <p id={hintId} className="text-xs text-ink-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-xs font-medium text-danger-600">
          {error}
        </p>
      )}
    </div>
  )
}

type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  label: string
  error?: string | undefined
  hint?: string | undefined
  wrapperClassName?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, required, className, wrapperClassName, ...rest },
  ref,
) {
  return (
    <Field
      label={label}
      {...(error === undefined ? {} : { error })}
      {...(hint === undefined ? {} : { hint })}
      {...(required === undefined ? {} : { required })}
      {...(wrapperClassName === undefined ? {} : { className: wrapperClassName })}
    >
      {({ id, describedBy, invalid }) => (
        <input
          ref={ref}
          id={id}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          required={required}
          className={cn(CONTROL, invalid ? 'border-danger-500' : 'border-ink-200', className)}
          {...rest}
        />
      )}
    </Field>
  )
})

type TextareaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id'> & {
  label: string
  error?: string | undefined
  hint?: string | undefined
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, error, hint, required, className, ...rest },
  ref,
) {
  return (
    <Field
      label={label}
      {...(error === undefined ? {} : { error })}
      {...(hint === undefined ? {} : { hint })}
      {...(required === undefined ? {} : { required })}
    >
      {({ id, describedBy, invalid }) => (
        <textarea
          ref={ref}
          id={id}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          required={required}
          className={cn(CONTROL, invalid ? 'border-danger-500' : 'border-ink-200', className)}
          {...rest}
        />
      )}
    </Field>
  )
})

type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id'> & {
  label: string
  error?: string | undefined
  hint?: string | undefined
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, error, hint, required, className, children, ...rest },
  ref,
) {
  return (
    <Field
      label={label}
      {...(error === undefined ? {} : { error })}
      {...(hint === undefined ? {} : { hint })}
      {...(required === undefined ? {} : { required })}
    >
      {({ id, describedBy, invalid }) => (
        <select
          ref={ref}
          id={id}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          required={required}
          className={cn(CONTROL, 'pr-8', invalid ? 'border-danger-500' : 'border-ink-200', className)}
          {...rest}
        >
          {children}
        </select>
      )}
    </Field>
  )
})

export function Checkbox({
  label,
  description,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode; description?: string }) {
  const id = useId()
  return (
    <div className="flex items-start gap-3">
      <input
        id={id}
        type="checkbox"
        className="mt-0.5 size-4 shrink-0 rounded border-ink-300 text-brand-600 focus:ring-brand-500"
        {...rest}
      />
      <label htmlFor={id} className="text-sm text-ink-700">
        {label}
        {description && <span className="block text-xs text-ink-500">{description}</span>}
      </label>
    </div>
  )
}
