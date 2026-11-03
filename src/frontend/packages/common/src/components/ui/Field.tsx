import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { useId } from 'react'
import { cx } from '../../utils/format'

interface FieldShellProps {
  label?: string
  hint?: string
  error?: string
  required?: boolean
  htmlFor?: string
  children: ReactNode
  aside?: ReactNode
}

export function FieldShell({ label, hint, error, required, htmlFor, children, aside }: FieldShellProps) {
  return (
    <div className="field">
      {(label || aside) && (
        <div className="field__head">
          {label && (
            <label className="field__label" htmlFor={htmlFor}>
              {label}
              {required && <span className="field__required"> *</span>}
            </label>
          )}
          {aside}
        </div>
      )}
      {children}
      {hint && !error && <p className="field__hint">{hint}</p>}
      {error && <p className="field__error">{error}</p>}
    </div>
  )
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  hint?: string
  error?: string
  aside?: ReactNode
}

export function Input({ label, hint, error, aside, className, id, ...rest }: InputProps) {
  const generated = useId()
  const inputId = id || generated
  return (
    <FieldShell label={label} hint={hint} error={error} required={rest.required} htmlFor={inputId} aside={aside}>
      <input
        id={inputId}
        className={cx('input', error && 'input--error', className)}
        aria-invalid={error ? true : undefined}
        {...rest}
      />
    </FieldShell>
  )
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  hint?: string
  error?: string
}

export function Textarea({ label, hint, error, className, id, ...rest }: TextareaProps) {
  const generated = useId()
  const inputId = id || generated
  return (
    <FieldShell label={label} hint={hint} error={error} required={rest.required} htmlFor={inputId}>
      <textarea
        id={inputId}
        className={cx('input', 'input--textarea', error && 'input--error', className)}
        aria-invalid={error ? true : undefined}
        {...rest}
      />
    </FieldShell>
  )
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  hint?: string
  error?: string
}

export function Select({ label, hint, error, className, id, children, ...rest }: SelectProps) {
  const generated = useId()
  const inputId = id || generated
  return (
    <FieldShell label={label} hint={hint} error={error} required={rest.required} htmlFor={inputId}>
      <div className="select-wrap">
        <select
          id={inputId}
          className={cx('input', 'select', error && 'input--error', className)}
          aria-invalid={error ? true : undefined}
          {...rest}
        >
          {children}
        </select>
        <span className="select-wrap__chevron" aria-hidden="true">
          ▾
        </span>
      </div>
    </FieldShell>
  )
}
