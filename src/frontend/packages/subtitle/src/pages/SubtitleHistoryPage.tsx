import { useState } from 'react'
import {
  ErrorState,
  Link,
  LoadingState,
  PageTitle,
  Pagination,
  relativeDate,
  useAsync,
  useDocumentTitle,
  useSession,
} from '@mugiko/common'
import { getSubtitleHistory } from '../libs/subtitles'
import { displayVideoName } from '../utils/video'
import { VideoThumbnail } from '../components/VideoThumbnail'

export function SubtitleHistoryPage() {
  useDocumentTitle('Subtitle history')
  const { revision } = useSession()
  const [page, setPage] = useState(1)
  const pageSize = 20
  const history = useAsync(
    (signal) => getSubtitleHistory(pageSize, (page - 1) * pageSize),
    [page, revision],
  )

  const totalPages = history.data ? Math.max(1, Math.ceil(history.data.total / pageSize)) : 1

  return (
    <div className="page">
      <PageTitle title="History" actions={<Link to="/subtitle">← Search</Link>} />

      {history.loading && <LoadingState label="Loading history" />}
      {history.error && (
        <ErrorState
          message={history.error}
          forbidden={history.forbidden}
          onRetry={history.reload}
        />
      )}

      {!history.loading && !history.error && history.data && history.data.items.length === 0 && (
        <p className="status">No history.</p>
      )}

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
            {history.data.items.map((item) => (
              <tr key={item.subtitle_id}>
                <td>
                  <div className="history-video">
                    <VideoThumbnail url={item.video_url} />
                    <div className="history-video__info">
                      <Link to={`/subtitle/${item.subtitle_id}`}>
                        {displayVideoName(item.video_url)}
                      </Link>
                      <br />
                      <span className="muted small">{item.video_url}</span>
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

      {history.data && history.data.total > pageSize && (
        <Pagination page={page} totalPages={totalPages} total={history.data.total} onChange={setPage} />
      )}
    </div>
  )
}
