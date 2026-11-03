import { useEffect, useState } from 'react'
import { Link, checkHealth, useDocumentTitle } from '@mugiko/common'

const SITES = [
  { to: '/subtitle', label: 'Subtitles' },
  { to: '/webnovel', label: 'Webnovel' },
  { to: '/decks', label: 'Decks' },
  { to: '/lookup', label: 'Lookup' },
  { to: '/ai', label: 'AI' },
]

export function HomePage() {
  useDocumentTitle()
  const [apiOnline, setApiOnline] = useState<boolean | null>(null)

  useEffect(() => {
    let alive = true
    checkHealth().then((ok) => {
      if (alive) setApiOnline(ok)
    })
    return () => {
      alive = false
    }
  }, [])

  return (
    <div className="page">
      <h1>Mugiko</h1>

      <table>
        <thead>
          <tr>
            <th>Site</th>
          </tr>
        </thead>
        <tbody>
          {SITES.map((site) => (
            <tr key={site.to}>
              <td>
                <Link to={site.to}>{site.label}</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="status">API: {apiOnline === null ? 'checking…' : apiOnline ? 'online' : 'offline'}</p>
    </div>
  )
}
