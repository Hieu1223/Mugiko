import { cx, padNumber } from '../../utils/format'

interface PaginationProps {
  page: number
  totalPages: number
  total?: number
  onChange: (page: number) => void
  busy?: boolean
}

export function Pagination({ page, totalPages, total, onChange, busy }: PaginationProps) {
  const safeTotal = Math.max(totalPages || 1, 1)
  if (safeTotal <= 1 && !total) return null

  const pages = pageWindow(page, safeTotal)

  return (
    <nav className="pagination" aria-label="Pagination">
      <button
        type="button"
        className="pagination__step"
        disabled={page <= 1 || busy}
        onClick={() => onChange(page - 1)}
      >
        Prev
      </button>
      <div className="pagination__pages">
        {pages.map((item, index) =>
          item === 'gap' ? (
            <span key={`gap-${index}`} className="pagination__gap">
              …
            </span>
          ) : (
            <button
              key={item}
              type="button"
              className={cx('pagination__page', item === page && 'is-active')}
              aria-current={item === page ? 'page' : undefined}
              disabled={busy}
              onClick={() => onChange(item)}
            >
              {padNumber(item)}
            </button>
          ),
        )}
      </div>
      <button
        type="button"
        className="pagination__step"
        disabled={page >= safeTotal || busy}
        onClick={() => onChange(page + 1)}
      >
        Next
      </button>
      {total !== undefined && <span className="pagination__meta">{total} total</span>}
    </nav>
  )
}

function pageWindow(current: number, total: number): Array<number | 'gap'> {
  if (total <= 7) return Array.from({ length: total }, (_, index) => index + 1)
  const pages = new Set<number>([1, total, current, current - 1, current + 1])
  const sorted = [...pages].filter((value) => value >= 1 && value <= total).sort((a, b) => a - b)
  const result: Array<number | 'gap'> = []
  sorted.forEach((value, index) => {
    if (index > 0 && value - sorted[index - 1] > 1) result.push('gap')
    result.push(value)
  })
  return result
}
