import type { ReactNode } from 'react'
import { cx } from '../../utils/format'

interface PageTitleProps {
  eyebrow?: string
  title: string
  lede?: ReactNode
  actions?: ReactNode
  mark?: string
  className?: string
}

/**
 * Page titles live inside <main>. The only <header> element on a page is the
 * shared Shell header, so each page has exactly one header.
 */
export function PageTitle({ title, actions, className }: PageTitleProps) {
  return (
    <div className={cx('page-head', className)}>
      <div className="page-head__main">
        <h1 className="page-head__title">{title}</h1>
      </div>
      {actions && <div className="page-head__actions">{actions}</div>}
    </div>
  )
}

interface TabsProps<T extends string> {
  tabs: Array<{ id: T; label: string; count?: number }>
  value: T
  onChange: (id: T) => void
  ariaLabel?: string
}

export function Tabs<T extends string>({ tabs, value, onChange, ariaLabel }: TabsProps<T>) {
  return (
    <div className="tabs" role="tablist" aria-label={ariaLabel}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={tab.id === value}
          className={cx('tab', tab.id === value && 'is-active')}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
          {tab.count !== undefined && <span className="tab__count">{tab.count}</span>}
        </button>
      ))}
    </div>
  )
}
