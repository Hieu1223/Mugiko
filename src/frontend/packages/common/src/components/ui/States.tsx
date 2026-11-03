import type { ReactNode } from 'react'
import { cx } from '../../utils/format'
import { Button } from './Button'

export function LoadingState({ label = 'Loading' }: { label?: string; rows?: number }) {
  return (
    <p className="status" role="status">
      {label}…
    </p>
  )
}

export function EmptyState({
  title,
  action,
}: {
  title: string
  message?: ReactNode
  action?: ReactNode
  mark?: string
}) {
  return (
    <div className="state state--empty">
      <p className="state__title">{title}</p>
      {action && <div className="state__action">{action}</div>}
    </div>
  )
}

export function ErrorState({
  message,
  onRetry,
  forbidden,
}: {
  title?: string
  message?: string
  onRetry?: () => void
  forbidden?: boolean
}) {
  return (
    <div className={cx('state', forbidden ? 'state--forbidden' : 'state--error')}>
      <p className="state__title">{forbidden ? 'Forbidden' : 'Error'}</p>
      <p className="state__message">{message || 'Request failed.'}</p>
      {onRetry && (
        <div className="state__action">
          <Button size="sm" onClick={onRetry}>
            Retry
          </Button>
        </div>
      )}
    </div>
  )
}

export function InlineNotice({
  tone = 'info',
  children,
  onDismiss,
}: {
  tone?: 'info' | 'error' | 'success' | 'warning'
  children: ReactNode
  onDismiss?: () => void
}) {
  return (
    <div className={cx('notice', `notice--${tone}`)} role={tone === 'error' ? 'alert' : 'status'}>
      <span className="notice__body">{children}</span>
      {onDismiss && (
        <button type="button" className="notice__close" onClick={onDismiss} aria-label="Dismiss">
          ×
        </button>
      )}
    </div>
  )
}
