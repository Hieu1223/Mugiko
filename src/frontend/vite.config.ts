import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv, type Connect, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const html = (path: string) => fileURLToPath(new URL(path, import.meta.url))

const legacyRoutes: Array<{ pattern: RegExp; to: (id: string) => string }> = [
  {
    pattern: /^\/decks\/([^/]+)$/,
    to: (id) => `/decks/detail/?deckId=${encodeURIComponent(id)}`,
  },
  {
    pattern: /^\/webnovel\/chapters\/([^/]+)$/,
    to: (id) => `/webnovel/reader/?chapterId=${encodeURIComponent(id)}`,
  },
  {
    pattern: /^\/subtitle\/([^/]+)$/,
    to: (id) => `/subtitle/viewer/?subtitleId=${encodeURIComponent(id)}`,
  },
  {
    pattern: /^\/webnovel\/([^/]+)$/,
    to: (id) => `/webnovel/detail/?novelId=${encodeURIComponent(id)}`,
  },
]

/**
 * Dev/preview helper for the static MPA:
 * - redirect /subtitle to /subtitle/ (directory index)
 * - redirect old path-style URLs to their query-param pages
 * - render 404.html for unknown pages
 *
 * A static host should be configured to do the same (serve directory
 * indexes and a 404.html fallback).
 */
function mpaFallback(): Plugin {
  const middleware = (root: string): Connect.NextHandleFunction => (req, res, next) => {
    if (req.method !== 'GET' && req.method !== 'HEAD') return next()
    const raw = req.url
    if (!raw || !raw.startsWith('/') || raw.startsWith('/api') || raw.startsWith('/health')) {
      return next()
    }

    const accept = req.headers.accept
    if (accept && !accept.includes('text/html') && !accept.includes('*/*')) return next()

    const [rawPath = '/', query = ''] = raw.split('?')
    let pathname: string
    try {
      pathname = decodeURIComponent(rawPath)
    } catch {
      return next()
    }

    if (pathname === '/subtitle/create' || pathname === '/subtitle/create/') {
      const params = new URLSearchParams(query)
      params.set('create', '1')
      res.statusCode = 301
      res.setHeader('Location', `/subtitle/?${params.toString()}`)
      res.end()
      return
    }

    if (pathname === '/' || pathname.endsWith('/')) return next()
    if (/\.[^/]+$/.test(pathname)) return next()
    if (
      pathname.startsWith('/@') ||
      pathname.startsWith('/src/') ||
      pathname.startsWith('/packages/') ||
      pathname.startsWith('/node_modules/')
    ) {
      return next()
    }

    const suffix = query ? `?${query}` : ''
    const candidate = resolve(root, pathname.slice(1), 'index.html')
    if (existsSync(candidate)) {
      res.statusCode = 301
      res.setHeader('Location', `${pathname}/${suffix}`)
      res.end()
      return
    }

    for (const route of legacyRoutes) {
      const match = pathname.match(route.pattern)
      if (match) {
        res.statusCode = 302
        res.setHeader('Location', route.to(match[1]))
        res.end()
        return
      }
    }

    res.statusCode = 404
    req.url = `/404.html${suffix}`
    next()
  }

  return {
    name: 'mugiko-mpa-fallback',
    configureServer(server) {
      server.middlewares.use(middleware(server.config.root))
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware(resolve(server.config.root, server.config.build.outDir)))
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_API_PROXY_TARGET || 'http://localhost:8080'

  return {
    // Real HTML documents at clean URLs, not a single SPA shell.
    appType: 'mpa',
    plugins: [react(), mpaFallback()],
    resolve: {
      alias: {
        '@mugiko/common': html('./packages/common/src/index.ts'),
        '@mugiko/subtitle': html('./packages/subtitle/src/index.tsx'),
        '@mugiko/webnovel': html('./packages/webnovel/src/index.tsx'),
        '@mugiko/ai': html('./packages/ai/src/index.tsx'),
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': { target, changeOrigin: true },
        '/health': { target, changeOrigin: true },
      },
    },
    build: {
      rollupOptions: {
        input: {
          home: html('./index.html'),
          ai: html('./ai/index.html'),
          lookup: html('./lookup/index.html'),
          decks: html('./decks/index.html'),
          'deck-detail': html('./decks/detail/index.html'),
          subtitle: html('./subtitle/index.html'),
          'subtitle-providers': html('./subtitle/providers/index.html'),
          'subtitle-history': html('./subtitle/history/index.html'),
          'subtitle-settings': html('./subtitle/settings/index.html'),
          'subtitle-viewer': html('./subtitle/viewer/index.html'),
          webnovel: html('./webnovel/index.html'),
          'webnovel-add': html('./webnovel/add/index.html'),
          'webnovel-search': html('./webnovel/search/index.html'),
          'webnovel-detail': html('./webnovel/detail/index.html'),
          'webnovel-reader': html('./webnovel/reader/index.html'),
          'not-found': html('./404.html'),
        },
      },
    },
  }
})
