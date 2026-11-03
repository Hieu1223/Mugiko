import { useEffect, useMemo } from 'react'
import {
  ErrorState,
  Link,
  LoadingState,
  normalizeTokens,
  useAsync,
  useDocumentTitle,
  useParams,
  useSession,
  WordToken,
  type WordTokenMode,
} from '@mugiko/common'
import { getChapter, getNovel } from '../libs/novels'
import { rememberPosition, useReaderSettings } from '../libs/preferences'
import type { Paragraph } from '../libs/types'

export function WebNovelReaderPage() {
  const { chapterId = '' } = useParams()
  const { revision } = useSession()
  const [settings, setSettings] = useReaderSettings()
  useDocumentTitle('Reader')

  const chapter = useAsync((signal) => getChapter(chapterId), [chapterId, revision], {
    enabled: Boolean(chapterId),
  })

  const novel = useAsync(
    (signal) => (chapter.data ? getNovel(chapter.data.novel_id) : Promise.resolve(null)),
    [chapter.data?.novel_id, revision],
    { enabled: Boolean(chapter.data?.novel_id) },
  )

  const paragraphs = useMemo(
    () => [...(chapter.data?.paragraphs || [])].sort((a, b) => a.idx - b.idx),
    [chapter.data],
  )

  const chapters = useMemo(
    () => [...(novel.data?.chapters || [])].sort((a, b) => a.idx - b.idx),
    [novel.data],
  )

  const currentIndex = chapters.findIndex((item) => item.id === chapterId)
  const previous = currentIndex > 0 ? chapters[currentIndex - 1] : null
  const next = currentIndex >= 0 && currentIndex < chapters.length - 1 ? chapters[currentIndex + 1] : null

  useEffect(() => {
    if (!chapter.data) return
    rememberPosition(chapter.data.novel_id, {
      chapterId: chapter.data.id,
      chapterTitle: chapter.data.title,
      chapterIdx: chapter.data.idx,
      updatedAt: Date.now(),
    })
    window.scrollTo({ top: 0 })
  }, [chapter.data])

  if (chapter.loading) {
    return (
      <div className="page">
        <LoadingState label="Loading chapter" />
      </div>
    )
  }

  if (chapter.error || !chapter.data) {
    return (
      <div className="page">
        <ErrorState
          message={chapter.error || 'Chapter not found.'}
          forbidden={chapter.forbidden}
          onRetry={chapter.reload}
        />
        <p>
          <Link to="/webnovel">← Library</Link>
        </p>
      </div>
    )
  }

  const data = chapter.data

  return (
    <div className="page reader">
      <div className="reader__toolbar">
        <div className="reader__crumb">
          <Link to="/webnovel">Library</Link>
          <span>/</span>
          {novel.data ? (
            <Link to={`/webnovel/${novel.data.id}`}>{novel.data.title}</Link>
          ) : (
            <span>Novel</span>
          )}
          <span>/</span>
          <span>Ch. {String(data.idx).padStart(3, '0')}</span>
        </div>
        <div className="reader__controls">
          <label className="reader__control">
            Size{' '}
            <input
              type="range"
              min={0.85}
              max={1.5}
              step={0.05}
              value={settings.fontScale}
              onChange={(event) =>
                setSettings((current) => ({ ...current, fontScale: Number(event.target.value) }))
              }
            />
          </label>
          <label className="reader__control">
            Width{' '}
            <input
              type="range"
              min={50}
              max={100}
              step={5}
              value={settings.widthPercent}
              onChange={(event) =>
                setSettings((current) => ({ ...current, widthPercent: Number(event.target.value) }))
              }
            />
          </label>
          <label className="reader__control">
            <input
              type="checkbox"
              checked={settings.showFurigana}
              onChange={(event) =>
                setSettings((current) => ({ ...current, showFurigana: event.target.checked }))
              }
            />{' '}
            Furigana
          </label>
        </div>
      </div>

      <article
        className="reader__sheet"
        style={{
          ['--reader-scale' as string]: settings.fontScale,
          ['--reader-leading' as string]: settings.lineHeight,
          ['--reader-width' as string]: `${settings.widthPercent}%`,
        }}
      >
        <div className="reader__head">
          <h1 className="reader__title">{data.title || 'Untitled chapter'}</h1>
        </div>

        <div className="reader__body">
          {paragraphs.length === 0 && (
            <p className="muted">This chapter has no paragraphs yet.</p>
          )}
          {paragraphs.map((paragraph) => (
            <ParagraphView
              key={paragraph.id}
              paragraph={paragraph}
              displayMode={settings.showFurigana ? 'both' : 'normal'}
            />
          ))}
        </div>

        <footer className="reader__foot">
          <nav className="reader__pager" aria-label="Chapter navigation">
            {previous ? (
              <Link to={`/webnovel/chapters/${previous.id}`}>
                ← {previous.title || 'Previous'}
              </Link>
            ) : (
              <span />
            )}
            {next ? (
              <Link to={`/webnovel/chapters/${next.id}`}>{next.title || 'Next'} →</Link>
            ) : (
              <span className="muted">End</span>
            )}
          </nav>
          <p>
            <Link to={novel.data ? `/webnovel/${novel.data.id}` : '/webnovel'}>Contents</Link>
          </p>
        </footer>
      </article>
    </div>
  )
}

function ParagraphView({
  paragraph,
  displayMode,
}: {
  paragraph: Paragraph
  displayMode: WordTokenMode
}) {
  const tokens = normalizeTokens(paragraph.words)

  return (
    <p className="reader__paragraph">
      {tokens.length > 0 ? (
        tokens.map((token, index) => (
          <WordToken key={`${paragraph.id}-${index}`} token={token} displayMode={displayMode} />
        ))
      ) : (
        paragraph.text
      )}
    </p>
  )
}
