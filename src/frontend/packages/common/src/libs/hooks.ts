import { useCallback, useEffect, useRef, useState } from 'react'
import { errorDetail, isApiError } from '../libs/api'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
  forbidden: boolean
  unauthorized: boolean
  reload: () => void
  setData: (value: T | null) => void
}

/**
 * Small abortable fetch hook. `deps` should include every value used by the loader.
 * The loader receives the abort signal; ignore it if the request API cannot accept one.
 */
export function useAsync<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  deps: unknown[],
  options: { enabled?: boolean } = {},
): AsyncState<T> {
  const { enabled = true } = options
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [unauthorized, setUnauthorized] = useState(false)
  const [nonce, setNonce] = useState(0)
  const loaderRef = useRef(loader)
  loaderRef.current = loader

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    const controller = new AbortController()
    let alive = true
    setLoading(true)
    setError(null)
    setForbidden(false)
    setUnauthorized(false)

    loaderRef.current(controller.signal)
      .then((value) => {
        if (!alive) return
        setData(value)
        setLoading(false)
      })
      .catch((err) => {
        if (!alive || (err instanceof DOMException && err.name === 'AbortError')) return
        setError(errorDetail(err))
        setForbidden(isApiError(err) && err.status === 403)
        setUnauthorized(isApiError(err) && err.status === 401)
        setLoading(false)
      })

    return () => {
      alive = false
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, nonce, ...deps])

  const reload = useCallback(() => setNonce((value) => value + 1), [])

  return { data, loading, error, forbidden, unauthorized, reload, setData }
}

export function useDebounced<T>(value: T, delay = 180): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay)
    return () => window.clearTimeout(timer)
  }, [value, delay])
  return debounced
}

export function useDocumentTitle(title?: string) {
  useEffect(() => {
    const base = 'MUGIKO'
    document.title = title ? `${title} // ${base}` : `${base} // Japanese Language Toolkit`
  }, [title])
}
