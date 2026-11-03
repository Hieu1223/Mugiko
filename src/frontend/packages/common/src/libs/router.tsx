import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type AnchorHTMLAttributes,
  type ReactNode,
} from 'react'

/**
 * The site is a multi-page Vite app. Each page is a real HTML document, so
 * navigation uses normal anchors and full document loads. These helpers keep
 * the existing page code readable while mapping the old path-style routes to
 * the static page URLs.
 */

export interface RouteParams {
  deckId?: string
  subtitleId?: string
  novelId?: string
  chapterId?: string
}

interface PageContextValue {
  page: string
  params: RouteParams
}

const PageContext = createContext<PageContextValue>({ page: 'home', params: {} })

export function readRouteParams(): RouteParams {
  const search = new URLSearchParams(window.location.search)
  return {
    deckId: search.get('deckId') ?? undefined,
    subtitleId: search.get('subtitleId') ?? undefined,
    novelId: search.get('novelId') ?? undefined,
    chapterId: search.get('chapterId') ?? undefined,
  }
}

export function PageProvider({
  page,
  params,
  children,
}: {
  page: string
  params: RouteParams
  children: ReactNode
}) {
  const value = useMemo(() => ({ page, params }), [page, params])
  return <PageContext.Provider value={value}>{children}</PageContext.Provider>
}

export function usePage(): PageContextValue {
  return useContext(PageContext)
}

export function useParams(): RouteParams {
  return useContext(PageContext).params
}

const STATIC_ROUTES: Record<string, string> = {
  '/': '/',
  '/ai': '/ai/',
  '/lookup': '/lookup/',
  '/decks': '/decks/',
  '/decks/detail': '/decks/detail/',
  '/subtitle': '/subtitle/',
  '/subtitle/providers': '/subtitle/providers/',
  '/subtitle/history': '/subtitle/history/',
  '/subtitle/settings': '/subtitle/settings/',
  '/subtitle/viewer': '/subtitle/viewer/',
  '/webnovel': '/webnovel/',
  '/webnovel/add': '/webnovel/add/',
  '/webnovel/search': '/webnovel/search/',
  '/webnovel/detail': '/webnovel/detail/',
  '/webnovel/reader': '/webnovel/reader/',
}

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

function withQueryAndHash(
  path: string,
  source: URL,
  params: Record<string, string> = {},
): string {
  const search = new URLSearchParams(source.search)
  for (const [key, value] of Object.entries(params)) search.set(key, value)
  const query = search.toString()
  return `${path}${query ? `?${query}` : ''}${source.hash}`
}

/** Map an old path-style route to the matching static HTML page. */
export function routeToHref(to: string): string {
  if (!to) return to
  if (to.startsWith('#')) return to
  if (/^[a-z][a-z0-9+.-]*:/i.test(to)) return to
  if (!to.startsWith('/')) return to

  const url = new URL(to, window.location.origin)
  const pathname = url.pathname.replace(/\/+$/, '') || '/'
  const staticPath = STATIC_ROUTES[pathname]
  if (staticPath) return withQueryAndHash(staticPath, url)

  const deck = pathname.match(/^\/decks\/([^/]+)$/)
  if (deck) {
    return withQueryAndHash('/decks/detail/', url, { deckId: safeDecode(deck[1]) })
  }

  const chapter = pathname.match(/^\/webnovel\/chapters\/([^/]+)$/)
  if (chapter) {
    return withQueryAndHash('/webnovel/reader/', url, {
      chapterId: safeDecode(chapter[1]),
    })
  }

  const subtitle = pathname.match(/^\/subtitle\/([^/]+)$/)
  if (subtitle) {
    if (subtitle[1] === 'create') {
      return withQueryAndHash('/subtitle/', url, { create: '1' })
    }
    return withQueryAndHash('/subtitle/viewer/', url, {
      subtitleId: safeDecode(subtitle[1]),
    })
  }

  const novel = pathname.match(/^\/webnovel\/([^/]+)$/)
  if (novel) {
    return withQueryAndHash('/webnovel/detail/', url, {
      novelId: safeDecode(novel[1]),
    })
  }

  return to
}

interface LinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'> {
  to: string
}

/**
 * A normal anchor. There is intentionally no client-side route interception:
 * every navigation is a full page load, which is the point of the MPA build.
 */
export function Link({ to, ...rest }: LinkProps) {
  return <a {...rest} href={routeToHref(to)} />
}

export function useNavigate() {
  return useCallback((to: string, options?: { replace?: boolean }) => {
    const href = routeToHref(to)
    if (options?.replace) window.location.replace(href)
    else window.location.assign(href)
  }, [])
}

type SearchParamsInit = URLSearchParams | Record<string, string>

export function useSearchParams(): [
  URLSearchParams,
  (next: SearchParamsInit, options?: { replace?: boolean }) => void,
] {
  const [params, setParamsState] = useState(
    () => new URLSearchParams(window.location.search),
  )

  useEffect(() => {
    const onPopState = () => {
      setParamsState(new URLSearchParams(window.location.search))
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const setParams = useCallback(
    (next: SearchParamsInit, options?: { replace?: boolean }) => {
      const search =
        next instanceof URLSearchParams ? next : new URLSearchParams(next)
      const query = search.toString()
      const url = `${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`
      if (options?.replace) window.history.replaceState(null, '', url)
      else window.history.pushState(null, '', url)
      setParamsState(new URLSearchParams(query))
    },
    [],
  )

  return [params, setParams]
}
