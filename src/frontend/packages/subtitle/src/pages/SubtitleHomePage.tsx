import { useState } from 'react'
import {
  Button,
  EmptyState,
  ErrorState,
  Input,
  Link,
  LoadingState,
  PageTitle,
  relativeDate,
  useAsync,
  useDocumentTitle,
  useSearchParams,
  useSession,
} from '@mugiko/common'
import { searchSubtitles, getSubtitleHistory } from '../libs/subtitles'
import type { SubtitleListItem } from '../libs/types'
import { displayVideoName } from '../utils/video'
import { CreateSubtitleDialog } from '../components/CreateSubtitleDialog'
import { VideoThumbnail } from '../components/VideoThumbnail'

export function SubtitleHomePage() {
  useDocumentTitle('Subtitles')
  const { revision } = useSession()
  const [searchParams, setSearchParams] = useSearchParams()
  const [createOpen, setCreateOpen] = useState(() => searchParams.get('create') === '1')
  const [url, setUrl] = useState('')
  const [submittedUrl, setSubmittedUrl] = useState('')
  const [page, setPage] = useState(1)

  const closeCreate = () => {
    setCreateOpen(false)
    if (searchParams.has('create')) {
      const next = new URLSearchParams(searchParams)
      next.delete('create')
      setSearchParams(next, { replace: true })
    }
  }

  const search = useAsync(
    (signal) => searchSubtitles({ video_url: submittedUrl, limit: 20, offset: (page - 1) * 20 }),
    [submittedUrl, page, revision],
    { enabled: Boolean(submittedUrl) },
  )

  const history = useAsync((signal) => getSubtitleHistory(8, 0), [revision])

  const results = search.data || []

  return (
    <div className="page">
      <PageTitle
        title="Subtitles"
        actions={
          <Button variant="primary" onClick={() => setCreateOpen(true)}>
            New subtitle
          </Button>
        }
      />

      <form
        className="form-row"
        onSubmit={(event) => {
          event.preventDefault()
          setPage(1)
          setSubmittedUrl(url.trim())
        }}
      >
        <Input
          label="Video URL"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="https://www.youtube.com/watch?v=…"
          autoComplete="off"
          spellCheck={false}
        />
        <Button type="submit" variant="primary">
          Search
        </Button>
        {(url || submittedUrl) && (
          <Button
            onClick={() => {
              setUrl('')
              setSubmittedUrl('')
              setPage(1)
            }}
          >
            Clear
          </Button>
        )}
      </form>

      <h2>Results</h2>

      {!submittedUrl && <p className="status">Enter a video URL.</p>}

      {search.loading && <LoadingState label="Searching subtitles" />}
      {search.error && (
        <ErrorState message={search.error} forbidden={search.forbidden} onRetry={search.reload} />
      )}

      {!search.loading && !search.error && submittedUrl && results.length === 0 && (
        <EmptyState title={submittedUrl ? 'No subtitle for this video.' : 'No subtitles.'} />
      )}

      {!search.loading && results.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Video</th>
              <th>Lines</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {results.map((item) => (
              <SubtitleRow key={item.id} item={item} />
            ))}
          </tbody>
        </table>
      )}

      {results.length >= 20 && (
        <p className="pager">
          <button type="button" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>
            Prev
          </button>
          <span className="pagination__meta">Page {page}</span>
          <button type="button" onClick={() => setPage((value) => value + 1)}>
            Next
          </button>
        </p>
      )}

      <h2>History</h2>
      {history.loading && <LoadingState label="Loading history" />}
      {history.error && !history.forbidden && <p className="status">History unavailable.</p>}
      {history.forbidden && <p className="status">History requires a user session.</p>}
      {history.data && history.data.items.length === 0 && <p className="status">No history.</p>}
      {history.data && history.data.items.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Video</th>
              <th>Lines</th>
              <th>Last opened</th>
            </tr>
          </thead>
          <tbody>
            {history.data.items.slice(0, 6).map((item) => (
              <tr key={item.subtitle_id}>
                <td>
                  <div className="history-video">
                    <VideoThumbnail url={item.video_url} />
                    <div className="history-video__info">
                      <Link to={`/subtitle/${item.subtitle_id}`}>
                        {displayVideoName(item.video_url)}
                      </Link>
                    </div>
                  </div>
                </td>
                <td>{item.segment_count ?? 0}</td>
                <td>{relativeDate(item.last_accessed_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p>
        <Link to="/subtitle/history">All history</Link>
      </p>

      {createOpen && <CreateSubtitleDialog onClose={closeCreate} />}
    </div>
  )
}

function SubtitleRow({ item }: { item: SubtitleListItem }) {
  return (
    <tr>
      <td>
        <Link to={`/subtitle/${item.id}`}>{displayVideoName(item.video_url)}</Link>
        {item.status && <span className="muted small"> · {item.status}</span>}
        <br />
        <span className="muted small">{item.video_url}</span>
      </td>
      <td>{item.segment_count ?? 0}</td>
      <td>{relativeDate(item.created_at)}</td>
    </tr>
  )
}
