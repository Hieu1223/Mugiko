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
} from '@mugiko/common'
import { getChapter, getManga, listMangaChapters } from '../libs/manga'
import type { ChapterSummary } from '../libs/types'

export function MangaReaderPage() {
  const chapterId = useParams().chapterId || ''
  useDocumentTitle('Reader')

  const chapter = useAsync((signal) => getChapter(chapterId, signal), [chapterId])
  const manga = useAsync(
    (signal) => (chapter.data ? getManga(chapter.data.manga_id, signal) : Promise.resolve(null)),
    [chapter.data?.manga_id],
  )
  const allChapters = useAsync(
    (signal) =>
      chapter.data
        ? listMangaChapters(chapter.data.manga_id, { page_size: 200, sort: 'source_index', order: 'asc' }, signal)
        : Promise.resolve(null),
    [chapter.data?.manga_id],
  )

  if (chapter.loading || manga.loading || allChapters.loading) {
    return (
      <div className="page">
        <PageTitle title="Reader" />
        <LoadingState label="Loading chapter" />
      </div>
    )
  }
  if (chapter.error || manga.error || allChapters.error) {
    return (
      <div className="page">
        <PageTitle title="Reader" />
        <ErrorState message={chapter.error || manga.error || allChapters.error || undefined} onRetry={chapter.reload} />
      </div>
    )
  }
  const chapterData = chapter.data
  const mangaData = manga.data
  const chapterList = allChapters.data
  if (!chapterData || !mangaData || !chapterList) {
    return (
      <div className="page">
        <PageTitle title="Reader" />
        <h1>Chapter not found.</h1>
      </div>
    )
  }

  const pages = chapterData.pages || []
  const index = chapterList.items.findIndex((item) => item.id === chapterData.id)
  const prev = index > 0 ? chapterList.items[index - 1] : null
  const next = index < chapterList.items.length - 1 ? chapterList.items[index + 1] : null

  return (
    <div className="page">
      <PageTitle title={`${mangaData.title} · Chapter ${chapterData.number}`} />

      <nav className="reader-nav">
        <Link to={`/manga/${mangaData.slug}`}>{mangaData.title}</Link>
        <span>Chapter {chapterData.number}</span>
        <div>
          {prev && (
            <Link to={`/manga/chapters/${prev.id}`} className="text-btn">
              ← {prev.number}
            </Link>
          )}
          <Link to={`/manga/${mangaData.slug}`}>Contents</Link>
          {next && (
            <Link to={`/manga/chapters/${next.id}`} className="text-btn">
              {next.number} →
            </Link>
          )}
        </div>
      </nav>

      <h1>Chapter {chapterData.number}</h1>
      {chapterData.title && <p>{chapterData.title}</p>}
      <p className="muted small">
        Published {formatDate(chapterData.published_at)} · {pages.length} page{pages.length !== 1 ? 's' : ''}
      </p>

      <div className="manga-pages">
        {pages.map((page) => (
          <img
            key={page.index}
            className="manga-page"
            src={page.url}
            alt={`Page ${page.index + 1}`}
            loading="lazy"
            decoding="async"
          />
        ))}
      </div>

      <nav className="reader-nav">
        <div>
          {prev && (
            <Link to={`/manga/chapters/${prev.id}`} className="text-btn">
              ← {prev.number}
            </Link>
          )}
          <Link to={`/manga/${mangaData.slug}`}>Contents</Link>
          {next && (
            <Link to={`/manga/chapters/${next.id}`} className="text-btn">
              {next.number} →
            </Link>
          )}
        </div>
      </nav>
    </div>
  )
}
