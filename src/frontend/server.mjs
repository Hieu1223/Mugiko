import { createReadStream, existsSync, statSync } from 'node:fs'
import { createServer, request as httpRequest } from 'node:http'
import { request as httpsRequest } from 'node:https'
import { extname, join, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const distDir = resolve(fileURLToPath(new URL('./dist', import.meta.url)))
const indexFile = join(distDir, 'index.html')
const port = Number(process.env.PORT || 3000)
const apiTarget = new URL(process.env.API_PROXY_TARGET || 'http://localhost:8080')

const contentTypes = {
  '.css': 'text/css; charset=utf-8',
  '.gif': 'image/gif',
  '.html': 'text/html; charset=utf-8',
  '.ico': 'image/x-icon',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ttf': 'font/ttf',
  '.txt': 'text/plain; charset=utf-8',
  '.webp': 'image/webp',
  '.webmanifest': 'application/manifest+json',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
}

function isApiRequest(url) {
  return (
    url === '/api' ||
    url.startsWith('/api/') ||
    url.startsWith('/api?') ||
    url === '/health' ||
    url.startsWith('/health?')
  )
}

function proxy(req, res) {
  const target = new URL(req.url || '/', apiTarget)
  const request = target.protocol === 'https:' ? httpsRequest : httpRequest

  const proxyReq = request(
    {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port || undefined,
      method: req.method,
      path: `${target.pathname}${target.search}`,
      headers: { ...req.headers, host: target.host },
    },
    (proxyRes) => {
      res.writeHead(proxyRes.statusCode || 502, proxyRes.headers)
      proxyRes.pipe(res)
    },
  )

  proxyReq.on('error', (error) => {
    console.error(`API proxy error: ${error.message}`)
    if (!res.headersSent) {
      res.writeHead(502, { 'content-type': 'application/json; charset=utf-8' })
    }
    res.end(JSON.stringify({ detail: 'API could not be reached.' }))
  })

  res.on('close', () => {
    if (!res.writableEnded) proxyReq.destroy()
  })

  req.pipe(proxyReq)
}

function serveFile(req, res, filePath) {
  const stat = statSync(filePath)
  const headers = {
    'content-type': contentTypes[extname(filePath).toLowerCase()] || 'application/octet-stream',
    'content-length': stat.size,
    'last-modified': stat.mtime.toUTCString(),
  }

  if (filePath === indexFile) {
    headers['cache-control'] = 'no-cache'
  } else if (filePath.includes(`${sep}assets${sep}`)) {
    headers['cache-control'] = 'public, max-age=31536000, immutable'
  }

  res.writeHead(200, headers)
  if (req.method === 'HEAD') {
    res.end()
    return
  }

  createReadStream(filePath).pipe(res)
}

const server = createServer((req, res) => {
  const url = req.url || '/'

  if (isApiRequest(url)) {
    proxy(req, res)
    return
  }

  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.writeHead(405, { allow: 'GET, HEAD' })
    res.end()
    return
  }

  let pathname
  try {
    pathname = decodeURIComponent(new URL(url, 'http://localhost').pathname)
  } catch {
    res.writeHead(400)
    res.end('Bad request')
    return
  }

  // Keep static document names out of the React routes.
  if (pathname.endsWith('/index.html')) {
    res.writeHead(301, { location: pathname.replace(/\/index\.html$/, '') || '/' })
    res.end()
    return
  }

  const relative = pathname.replace(/^\/+/, '')
  let filePath = resolve(distDir, relative)

  if (filePath !== distDir && !filePath.startsWith(`${distDir}${sep}`)) {
    res.writeHead(403)
    res.end('Forbidden')
    return
  }

  if (existsSync(filePath) && statSync(filePath).isDirectory()) {
    filePath = join(filePath, 'index.html')
  }

  if (!existsSync(filePath) || !statSync(filePath).isFile()) {
    // Missing asset files should stay 404s instead of returning the app shell.
    if (/\.[^/]+$/.test(pathname)) {
      res.writeHead(404)
      res.end('Not found')
      return
    }
    filePath = indexFile
  }

  serveFile(req, res, filePath)
})

server.listen(port, '0.0.0.0', () => {
  console.log(`Mugiko frontend listening on http://0.0.0.0:${port}`)
})

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    server.close(() => process.exit(0))
  })
}
