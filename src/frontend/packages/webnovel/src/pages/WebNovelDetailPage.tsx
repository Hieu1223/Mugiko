import { useMemo } from 'react'
import {
  Button,
  ErrorState,
  Link,
  LoadingState,
  PageTitle,
  formatDate,
  useAsync,
  useDocumentTitle,
  useParams,
  useSession,
} from '@mugiko/common'
import { getNovel } from '../libs/novels'
import { getRememberedPosition } from '../libs/preferences'

export function WebNovelDetailPage() {
  const { novelId = '' } = useParams()
  const { revision } = useSession()
  useDocumentTitle('Novel')

  const state = useAsync((signal) => getNovel(novelId), [novelId, revision], {
    enabled: Boolean(novelId),
  })

  const remembered = useMemo(() => (novelId ? getRememberedPosition(novelId) : null), [novelId])

  if (state.loading) {
    return (
      <div className="page">
        <LoadingState label="Loading novel" />
      </div>
    )
  }

  if (state.error || !state.data) {
    return (
      <div className="page">
        <h1>Novel</h1>
        <ErrorState
          message={state.error || 'Novel not found.'}
          forbidden={state.forbidden}
          onRetry={state.reload}
        />
        <p>
          <Link to="/webnovel">← Library</Link>
        </p>
      </div>
    )
  }

  const novel = state.data
  const chapters = [...(novel.chapters || [])].sort((a, b) => a.idx - b.idx)
  const startChapter = remembered
    ? chapters.find((chapter) => chapter.id === remembered.chapterId) || chapters[0]
    : chapters[0]

  return (
    <div className="page">
      <PageTitle
        title={novel.title}
        actions={
          <>
            {startChapter && (
              <Link to={`/webnovel/chapters/${startChapter.id}`}>
                {remembered ? 'Continue reading' : 'Start reading'}
              </Link>
            )}
            <Link to="/webnovel">← Library</Link>
          </>
        }
      />

      <table>
        <tbody>
          <tr>
            <th>Author</th>
            <td>{novel.author || '—'}</td>
          </tr>
          <tr>
            <th>Source</th>
            <td>{novel.source}</td>
          </tr>
          <tr>
            <th>Added</th>
            <td>{formatDate(novel.created_at)}</td>
          </tr>
          <tr>
            <th>Original</th>
            <td>
              <a href={novel.url} target="_blank" rel="noreferrer noopener">
                {novel.url}
              </a>
            </td>
          </tr>
        </tbody>
      </table>

      {novel.synopsis && (
        <>
          <h2>Synopsis</h2>
          <p>{novel.synopsis}</p>
        </>
      )}

      {remembered && (
        <p className="status">
          Last read: {remembered.chapterTitle || 'chapter'}.{' '}
          <Link to={`/webnovel/chapters/${remembered.chapterId}`}>Resume</Link>
        </p>
      )}

      <h2>Chapters · {chapters.length}</h2>

      {chapters.length === 0 ? (
        <div className="state">
          <p className="state__title">No chapters yet.</p>
          <Button size="sm" onClick={state.reload}>
            Refresh
          </Button>
        </div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Title</th>
            </tr>
          </thead>
          <tbody>
            {chapters.map((chapter) => {
              const isCurrent = remembered?.chapterId === chapter.id
              return (
                <tr key={chapter.id}>
                  <td>{String(chapter.idx).padStart(3, '0')}</td>
                  <td>
                    <Link to={`/webnovel/chapters/${chapter.id}`}>
                      {chapter.title || 'Untitled chapter'}
                    </Link>
                    {isCurrent && <span className="muted"> · current</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
