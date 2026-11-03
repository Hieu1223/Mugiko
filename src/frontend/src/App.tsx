import { lazy, Suspense, useMemo, type ReactNode } from 'react'
import {
  DeckDetailPage,
  DecksPage,
  LookupPage,
  PageProvider,
  readRouteParams,
  Shell,
  type SiteNav,
} from '@mugiko/common'
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

interface PageDefinition {
  render: () => ReactNode
}

const PAGES: Record<string, PageDefinition> = {
  home: { render: () => <HomePage /> },
  lookup: { render: () => <LookupPage /> },
  decks: { render: () => <DecksPage /> },
  'deck-detail': { render: () => <DeckDetailPage /> },
  'subtitle-home': { render: () => <SubtitleHomePage /> },
  'subtitle-viewer': { render: () => <SubtitleViewerPage /> },
  'subtitle-providers': { render: () => <SubtitleProvidersPage /> },
  'subtitle-history': { render: () => <SubtitleHistoryPage /> },
  'subtitle-settings': { render: () => <SubtitleSettingsPage /> },
  'webnovel-home': { render: () => <WebNovelHomePage /> },
  'webnovel-add': { render: () => <WebNovelAddPage /> },
  'webnovel-search': { render: () => <WebNovelSearchPage /> },
  'webnovel-detail': { render: () => <WebNovelDetailPage /> },
  'webnovel-reader': { render: () => <WebNovelReaderPage /> },
  ai: { render: () => <AIPage /> },
  'not-found': { render: () => <NotFoundPage /> },
}

export function App({ page }: { page: string }) {
  const resolvedPage = PAGES[page] ? page : 'not-found'
  const definition = PAGES[resolvedPage]
  const params = useMemo(readRouteParams, [])

  return (
    <PageProvider page={resolvedPage} params={params}>
      <Shell siteNavs={SITE_NAVS} activePage={resolvedPage}>
        <Suspense fallback={<p className="status">Loading…</p>}>
          {definition.render()}
        </Suspense>
      </Shell>
    </PageProvider>
  )
}
