import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link } from '../libs/router'
import { useSession } from '../libs/SessionContext'
import { cx } from '../utils/format'
import { SessionBadge } from './SessionBadge'
import { SessionDialog } from './SessionDialog'

export interface NavItem {
  to: string
  label: string
  page?: string
}

export interface SiteNav {
  id: string
  label: string
  base: string
  items: NavItem[]
}

const SITES: Array<{ id: string; label: string; to: string }> = [
  { id: 'home', label: 'Home', to: '/' },
  { id: 'subtitle', label: 'Subtitles', to: '/subtitle' },
  { id: 'webnovel', label: 'Webnovel', to: '/webnovel' },
  { id: 'decks', label: 'Decks', to: '/decks' },
  { id: 'lookup', label: 'Lookup', to: '/lookup' },
  { id: 'ai', label: 'AI', to: '/ai' },
  { id: 'manga', label: 'Manga', to: '/manga' },
]

function isSiteActive(activePage: string | undefined, siteId: string): boolean {
  if (!activePage) return false
  if (siteId === 'home') return activePage === 'home'
  if (siteId === 'subtitle') return activePage.startsWith('subtitle-')
  if (siteId === 'webnovel') return activePage.startsWith('webnovel-')
  if (siteId === 'decks') return activePage.startsWith('deck')
  if (siteId === 'lookup') return activePage === 'lookup'
  if (siteId === 'ai') return activePage === 'ai'
  if (siteId === 'manga') return activePage.startsWith('manga')
  return false
}

/**
 * The single shared header for every HTML page in the site.
 * Page content starts below this header inside <main>.
 */
export function Shell({
  children,
  siteNavs = [],
  activePage,
}: {
  children: ReactNode
  siteNavs?: SiteNav[]
  activePage?: string
}) {
  const [sessionOpen, setSessionOpen] = useState(false)
  const [openMenu, setOpenMenu] = useState<string | null>(null)
  const switcherRef = useRef<HTMLElement>(null)
  const { session, status, notice, dismissNotice, error, clearError } = useSession()

  // Close the dropdown after navigating to a new page.
  useEffect(() => {
    setOpenMenu(null)
  }, [activePage])

  useEffect(() => {
    if (!openMenu) return

    const onPointerDown = (event: PointerEvent) => {
      if (!switcherRef.current?.contains(event.target as Node)) setOpenMenu(null)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpenMenu(null)
    }

    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [openMenu])

  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>

      <header className="site-head">
        <div className="site-head__inner">
          <Link to="/" className="brand">
            Mugiko
          </Link>

          <nav ref={switcherRef} className="site-switcher" aria-label="Sites">
            {SITES.map((site) => {
              const active = isSiteActive(activePage, site.id)
              const siteNav = siteNavs.find((nav) => nav.id === site.id)
              const items = siteNav?.items ?? []
              const open = openMenu === site.id

              if (items.length === 0) {
                return (
                  <Link
                    key={site.id}
                    to={site.to}
                    className={cx('site-switcher__link', active && 'is-active')}
                    aria-current={active ? 'page' : undefined}
                  >
                    {site.label}
                  </Link>
                )
              }

              return (
                <div
                  key={site.id}
                  className={cx('site-menu', open && 'is-open')}
                  onBlur={(event) => {
                    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                      setOpenMenu((current) => (current === site.id ? null : current))
                    }
                  }}
                >
                  <button
                    type="button"
                    className={cx(
                      'site-switcher__link',
                      'site-menu__trigger',
                      active && 'is-active',
                    )}
                    aria-expanded={open}
                    aria-controls={`site-menu-${site.id}`}
                    onClick={() => setOpenMenu((current) => (current === site.id ? null : site.id))}
                  >
                    {site.label}
                    <span className="site-menu__caret" aria-hidden="true">
                      {open ? '▴' : '▾'}
                    </span>
                  </button>

                  {open && (
                    <nav
                      id={`site-menu-${site.id}`}
                      className="site-menu__panel"
                      aria-label={`${site.label} pages`}
                    >
                      {items.map((item) => {
                        const itemActive = Boolean(activePage && item.page === activePage)
                        return (
                          <Link
                            key={item.to}
                            to={item.to}
                            className={cx('site-menu__link', itemActive && 'is-active')}
                            aria-current={itemActive ? 'page' : undefined}
                            onClick={() => setOpenMenu(null)}
                          >
                            {item.label}
                          </Link>
                        )
                      })}
                    </nav>
                  )}
                </div>
              )
            })}
          </nav>

          <div className="site-head__tools">
            <SessionBadge onClick={() => setSessionOpen(true)} />
          </div>
        </div>
      </header>

      <hr />

      {status === 'error' && (
        <div className="banner banner--error" role="alert">
          <div className="banner__inner">
            <span className="banner__mark" aria-hidden="true">!</span>
            <span>API offline: {error || 'could not reach the backend'}</span>
            <button type="button" className="banner__action" onClick={clearError}>
              Dismiss
            </button>
          </div>
        </div>
      )}

      {notice && (
        <div className="banner banner--info">
          <div className="banner__inner">
            <span>{notice}</span>
            <button type="button" className="banner__action" onClick={dismissNotice}>
              OK
            </button>
          </div>
        </div>
      )}

      <main id="main" className="site-main">
        {children}
      </main>

      <hr />

      <footer className="site-foot">
        <div className="site-foot__inner">
          <div className="site-foot__brand">
            <span className="site-foot__name">Mugiko</span>
            <span>{session ? `${session.role} session` : 'no session'}</span>
          </div>
          <div className="site-foot__meta">
            <span>v0.1.0</span>
            <span>{new Date().getFullYear()}</span>
          </div>
        </div>
      </footer>

      <SessionDialog open={sessionOpen} onClose={() => setSessionOpen(false)} />
    </div>
  )
}
