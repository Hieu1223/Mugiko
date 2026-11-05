import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import {
  DeckDetailPage,
  DecksPage,
  LookupPage,
  Shell,
  isUuid,
  useParams,
  useSearchParams,
  type SiteNav,
} from '@mugiko/common'
import {
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import { HomePage } from './pages/HomePage'
import { NotFoundPage } from './pages/NotFoundPage'

const SubtitleHomePage = lazy(() =>
  import('@mugiko/subtitle').then((module) => ({ default: module.SubtitleHomePage })),
)
const SubtitleViewerPage = lazy(() =>
  import('@mugiko/subtitle').then((module) => ({ default: module.SubtitleViewerPage })),
)
const SubtitleProvidersPage = lazy(() =>
  import('@mugiko/subtitle').then((module) => ({ default: module.SubtitleProvidersPage })),
)
const SubtitleHistoryPage = lazy(() =>
  import('@mugiko/subtitle').then((module) => ({ default: module.SubtitleHistoryPage })),
)
const SubtitleSettingsPage = lazy(() =>
  import('@mugiko/subtitle').then((module) => ({ default: module.SubtitleSettingsPage })),
)

const WebNovelHomePage = lazy(() =>
  import('@mugiko/webnovel').then((module) => ({ default: module.WebNovelHomePage })),
)
const WebNovelAddPage = lazy(() =>
  import('@mugiko/webnovel').then((module) => ({ default: module.WebNovelAddPage })),
)
const WebNovelSearchPage = lazy(() =>
  import('@mugiko/webnovel').then((module) => ({ default: module.WebNovelSearchPage })),
)
const WebNovelDetailPage = lazy(() =>
  import('@mugiko/webnovel').then((module) => ({ default: module.WebNovelDetailPage })),
)
const WebNovelReaderPage = lazy(() =>
  import('@mugiko/webnovel').then((module) => ({ default: module.WebNovelReaderPage })),
)

const AIPage = lazy(() =>
  import('@mugiko/ai').then((module) => ({ default: module.AIPage })),
)

const subtitleNav: SiteNav = {
  id: 'subtitle',
  label: 'Subtitles',
  base: '/subtitle',
  items: [
    { to: '/subtitle', label: 'Search', page: 'subtitle-home' },
    { to: '/subtitle/providers', label: 'Providers', page: 'subtitle-providers' },
    { to: '/subtitle/history', label: 'History', page: 'subtitle-history' },
    { to: '/subtitle/settings', label: 'Settings', page: 'subtitle-settings' },
  ],
}

const webnovelNav: SiteNav = {
  id: 'webnovel',
  label: 'Webnovel',
  base: '/webnovel',
  items: [
    { to: '/webnovel', label: 'Library', page: 'webnovel-home' },
    { to: '/webnovel/add', label: 'Add', page: 'webnovel-add' },
    { to: '/webnovel/search', label: 'Search', page: 'webnovel-search' },
  ],
}

const SITE_NAVS: SiteNav[] = [subtitleNav, webnovelNav]

function activePageFor(rawPathname: string): string {
  const pathname = rawPathname.replace(/\/+$/, '') || '/'

  if (pathname === '/') return 'home'
  if (pathname === '/ai') return 'ai'
  if (pathname === '/lookup') return 'lookup'
  if (pathname === '/decks') return 'decks'
  if (pathname.startsWith('/decks/')) return 'deck-detail'

  if (pathname === '/subtitle') return 'subtitle-home'
  if (pathname === '/subtitle/providers') return 'subtitle-providers'
  if (pathname === '/subtitle/history') return 'subtitle-history'
  if (pathname === '/subtitle/settings') return 'subtitle-settings'
  if (pathname.startsWith('/subtitle/')) return 'subtitle-viewer'

  if (pathname === '/webnovel') return 'webnovel-home'
  if (pathname === '/webnovel/add') return 'webnovel-add'
  if (pathname === '/webnovel/search') return 'webnovel-search'
  if (pathname.startsWith('/webnovel/chapters/')) return 'webnovel-reader'
  if (pathname.startsWith('/webnovel/')) return 'webnovel-detail'

  return 'not-found'
}

function RequireUuid({
  param,
  redirectTo,
  children,
}: {
  param: string
  redirectTo: string
  children: ReactNode
}) {
  const params = useParams()
  if (!isUuid(params[param])) return <Navigate to={redirectTo} replace />
  return <>{children}</>
}

function LegacyQueryRedirect({
  param,
  fallback,
  build,
}: {
  param: string
  fallback: string
  build: (id: string) => string
}) {
  const [search] = useSearchParams()
  const id = search.get(param)
  return <Navigate to={id && isUuid(id) ? build(id) : fallback} replace />
}

function CatchAllPage() {
  const { pathname } = useLocation()
  if (pathname.endsWith('/index.html')) {
    const target = pathname.replace(/\/index\.html$/, '') || '/'
    return <Navigate to={target} replace />
  }
  return <NotFoundPage />
}

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export function App() {
  const location = useLocation()

  return (
    <>
      <ScrollToTop />
      <Shell siteNavs={SITE_NAVS} activePage={activePageFor(location.pathname)}>
        <Suspense fallback={<p className="status">Loading…</p>}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/ai" element={<AIPage />} />
            <Route path="/lookup" element={<LookupPage />} />

            <Route path="/decks" element={<DecksPage />} />
            <Route
              path="/decks/detail"
              element={
                <LegacyQueryRedirect
                  param="deckId"
                  fallback="/decks"
                  build={(id) => `/decks/${id}`}
                />
              }
            />
            <Route
              path="/decks/:deckId"
              element={
                <RequireUuid param="deckId" redirectTo="/decks">
                  <DeckDetailPage />
                </RequireUuid>
              }
            />

            <Route path="/subtitle" element={<SubtitleHomePage />} />
            <Route path="/subtitle/providers" element={<SubtitleProvidersPage />} />
            <Route path="/subtitle/history" element={<SubtitleHistoryPage />} />
            <Route path="/subtitle/settings" element={<SubtitleSettingsPage />} />
            <Route path="/subtitle/create" element={<Navigate to="/subtitle?create=1" replace />} />
            <Route
              path="/subtitle/viewer"
              element={
                <LegacyQueryRedirect
                  param="subtitleId"
                  fallback="/subtitle"
                  build={(id) => `/subtitle/${id}`}
                />
              }
            />
            <Route
              path="/subtitle/:subtitleId"
              element={
                <RequireUuid param="subtitleId" redirectTo="/subtitle">
                  <SubtitleViewerPage />
                </RequireUuid>
              }
            />

            <Route path="/webnovel" element={<WebNovelHomePage />} />
            <Route path="/webnovel/add" element={<WebNovelAddPage />} />
            <Route path="/webnovel/search" element={<WebNovelSearchPage />} />
            <Route
              path="/webnovel/detail"
              element={
                <LegacyQueryRedirect
                  param="novelId"
                  fallback="/webnovel"
                  build={(id) => `/webnovel/${id}`}
                />
              }
            />
            <Route
              path="/webnovel/reader"
              element={
                <LegacyQueryRedirect
                  param="chapterId"
                  fallback="/webnovel"
                  build={(id) => `/webnovel/chapters/${id}`}
                />
              }
            />
            <Route
              path="/webnovel/chapters/:chapterId"
              element={
                <RequireUuid param="chapterId" redirectTo="/webnovel">
                  <WebNovelReaderPage />
                </RequireUuid>
              }
            />
            <Route
              path="/webnovel/:novelId"
              element={
                <RequireUuid param="novelId" redirectTo="/webnovel">
                  <WebNovelDetailPage />
                </RequireUuid>
              }
            />

            <Route path="*" element={<CatchAllPage />} />
          </Routes>
        </Suspense>
      </Shell>
    </>
  )
}
