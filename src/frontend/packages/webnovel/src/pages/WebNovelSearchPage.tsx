import { useState } from 'react'
import {
  Button,
  ErrorState,
  Input,
  Link,
  LoadingState,
  PageTitle,
  useDocumentTitle,
} from '@mugiko/common'
import { searchNovels } from '../libs/novels'
import type { Novel } from '../libs/types'
import { NovelTable } from '../components/NovelCard'

export function WebNovelSearchPage() {
  useDocumentTitle('Search novels')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Novel[] | null>(null)
  const [total, setTotal] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forbidden, setForbidden] = useState(false)

  const run = async () => {
    const trimmed = query.trim()
    if (!trimmed) {
      setError('Enter a query.')
      return
    }
    setBusy(true)
    setError(null)
    setForbidden(false)
    try {
      const response = await searchNovels(trimmed, 30)
      setResults(response.items || [])
      setTotal(response.total ?? (response.items?.length || 0))
    } catch (err) {
      const status = (err as { status?: number }).status
      setForbidden(status === 403)
      setError(err instanceof Error ? err.message : 'Search failed.')
      setResults(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      <PageTitle title="Search" actions={<Link to="/webnovel/add">Add novel</Link>} />

      <form
        className="form-row"
        onSubmit={(event) => {
          event.preventDefault()
          void run()
        }}
      >
        <Input
          label="Query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Title, author, or keyword"
          autoFocus
        />
        <Button type="submit" variant="primary" loading={busy}>
          Search
        </Button>
      </form>

      {busy && <LoadingState label="Searching" />}
      {error && !busy && (
        <ErrorState message={error} forbidden={forbidden} onRetry={() => void run()} />
      )}

      {!busy && !error && results && results.length === 0 && (
        <p className="status">No matches.</p>
      )}

      {!busy && !error && results && results.length > 0 && (
        <>
          <h2>Results · {total}</h2>
          <NovelTable novels={results} />
        </>
      )}
    </div>
  )
}
