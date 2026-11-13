import { useMemo, useState } from 'react'
import {
  Button,
  ErrorState,
  Link,
  LoadingState,
  PageTitle,
  Pagination,
  formatDate,
  useAsync,
  useDocumentTitle,
  useParams,
} from '@mugiko/common'
import { getManga, listMangaChapters } from '../libs/manga'
import type { ChapterSummary } from '../libs/types'

const PAGE_SIZE = 50

export function MangaDetailPage() {
  const mangaId = useParams().mangaId || ''
  useDocumentTitle('Manga')

  const [chapterPage, setChapterPage] = useState(1)

  const detail = useAsync((signal) => getManga(mangaId, signal), [mangaId])
  const chapters = useAsync(
    (signal) =>
      listMangaChapters(mangaId, { page: chapterPage, page_size: PAGE_SIZE, sort: 'source_index', order: 'asc' }, signal),
    [mangaId, chapterPage],
  )

  const manga = detail.data
  const chapterData = chapters.data

  // Always call these hooks so hook order is stable across renders,
  // regardless of which early-return branch is taken below.
  const tags = useMemo(() => manga?.tags || [], [manga])
  const latest = useMemo(() => manga?.latest_chapters || [], [manga])

  if (detail.loading || chapters.loading) {
    return (
      <div className="page">
        <PageTitle title="Manga" />
        <LoadingState label="Loading manga" />
      </div>
    )
  }
  if (detail.error || chapters.error) {
    return (
      <div className="page">
        <PageTitle title="Manga" />
        <ErrorState message={detail.error || chapters.error || undefined} onRetry={detail.reload} forbidden={detail.forbidden} />
      </div>
    )
  }
  if (!manga || !chapterData) {
    return (
      <div className="page">
        <PageTitle title="Manga" />
        <h1>Manga not found.</h1>
      </div>
    )
  }

  const totalPages = Math.max(chapterData.total_pages || 1, 1)

  return (
    <div className="page">
      <PageTitle title={manga.title} />

      <div className="manga-detail">
        <div className="manga-detail__cover">
          {manga.cover_url ? (
            <img
              className="manga-detail__cover-img"
              src={manga.cover_url}
              alt={manga.title}
              loading="lazy"
              decoding="async"
            />
          ) : (
            <span className="manga-detail__cover--empty">no cover</span>
          )}
        </div>

        <div className="manga-detail__meta">
          {manga.alternative_titles && manga.alternative_titles.length > 0 && (
            <p className="manga-detail__alt">{manga.alternative_titles.join('; ')}</p>
          )}
          <div className="manga-detail__score">
            {manga.score > 0 ? `score: ${manga.score.toFixed(1)}` : ''}
            {manga.views > 0 ? ` · views: ${manga.views}` : ''}
          </div>
          <div className="manga-tags">
            {tags.map((tag) => (
              <span key={tag.slug} className="manga-tag">
                {tag.name}
              </span>
            ))}
          </div>
          {manga.description && (
            <div className="manga-detail__desc">
              <p>{manga.description}</p>
            </div>
          )}
          {manga.source_url && (
            <p className="manga-detail__source">
              Source: <Link to={manga.source_url} rel="nofollow">{manga.source_url}</Link>
            </p>
          )}
          <p className="manga-detail__meta-line">
            Created: {formatDate(manga.created_at)} · Updated: {formatDate(manga.updated_at)}
          </p>
        </div>
      </div>

      <div className="manga-chapters">
        <h2>Chapters ({chapterData.total})</h2>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Title</th>
              <th>Published</th>
              <th>Pages</th>
            </tr>
          </thead>
          <tbody>
            {chapterData.items.map((chapter) => (
              <tr key={chapter.id}>
                <td>{chapter.number}</td>
                <td>
                  <Link to={`/manga/chapters/${chapter.id}`}>{chapter.title || chapter.number}</Link>
                </td>
                <td>{formatDate(chapter.published_at)}</td>
                <td>{chapter.page_count}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <Pagination
          page={chapterPage}
          totalPages={totalPages}
          total={chapterData.total}
          onChange={setChapterPage}
        />

        {latest.length > 0 && (
          <div className="manga-latest">
            <h3>Latest chapters</h3>
            <ul>
              {latest.map((chapter) => (
                <li key={chapter.id}>
                  <Link to={`/manga/chapters/${chapter.id}`}>
                    {chapter.title || chapter.number}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
