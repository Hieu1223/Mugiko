import { Fragment, useEffect, useRef } from 'react'
import { WordToken, type WordTokenMode } from '@mugiko/common'
import type { DualSubtitleOrder } from '../libs/preferences'
import type { CueSegment, SubtitleLine } from '../utils/cues'

interface SegmentListProps {
  lines: SubtitleLine[]
  activeIndex: number
  autoScroll: boolean
  showTimestamps: boolean
  displayMode: WordTokenMode
  fontScale: number
  lookupEnabled: boolean
  order?: DualSubtitleOrder
  primaryLanguage?: string
  secondaryLanguage?: string
  primaryWordSpacing?: boolean
  secondaryWordSpacing?: boolean
  onSeek: (ms: number) => void
}

interface LineEntry {
  key: 'primary' | 'secondary'
  cue: CueSegment
  wordSpacing: boolean
  language?: string
}

export function SegmentList({
  lines,
  activeIndex,
  autoScroll,
  showTimestamps,
  displayMode,
  fontScale,
  lookupEnabled,
  order = 'primary-first',
  primaryLanguage,
  secondaryLanguage,
  primaryWordSpacing = false,
  secondaryWordSpacing = false,
  onSeek,
}: SegmentListProps) {
  const listRef = useRef<HTMLOListElement>(null)

  useEffect(() => {
    if (!autoScroll) return
    const list = listRef.current
    if (!list) return
    const node = list.querySelector<HTMLElement>(`[data-cue-index="${activeIndex}"]`)
    if (!node) return
    const listRect = list.getBoundingClientRect()
    const nodeRect = node.getBoundingClientRect()
    const target =
      list.scrollTop + (nodeRect.top - listRect.top) - list.clientHeight / 2 + node.clientHeight / 2
    list.scrollTo({ top: Math.max(0, target) })
  }, [activeIndex, autoScroll])

  if (lines.length === 0) {
    return <p className="status">No segments.</p>
  }

  const dual = Boolean(secondaryLanguage)

  return (
    <ol className="segment-list" ref={listRef}>
      {lines.map((line, index) => {
        const isActive = index === activeIndex
        const entries: LineEntry[] = []
        if (line.primary) {
          entries.push({
            key: 'primary',
            cue: line.primary,
            wordSpacing: primaryWordSpacing,
            language: primaryLanguage,
          })
        }
        if (line.secondary) {
          entries.push({
            key: 'secondary',
            cue: line.secondary,
            wordSpacing: secondaryWordSpacing,
            language: secondaryLanguage,
          })
        }
        if (order === 'secondary-first') entries.reverse()

        return (
          <li
            key={line.id}
            data-cue-index={index}
            className={`segment ${isActive ? 'is-active' : ''}`}
            onClick={() => onSeek(line.startMs)}
          >
            <div className="segment__row">
              <button
                type="button"
                className="segment__time"
                onClick={(event) => {
                  event.stopPropagation()
                  onSeek(line.startMs)
                }}
              >
                {String(index + 1).padStart(3, '0')}{' '}
                {showTimestamps ? formatCueTime(line.startMs) : ''}
              </button>

              <span
                className="segment__lines"
                style={{ fontSize: `${0.98 * fontScale}em` }}
              >
                {entries.map((entry) => (
                  <span
                    key={entry.key}
                    className={`segment__line segment__line--${entry.key}`}
                  >
                    {dual && entry.language && (
                      <span className="segment__lang">{entry.language.toUpperCase()}</span>
                    )}
                    <span className="segment__text">
                      <CueText
                        cue={entry.cue}
                        displayMode={displayMode}
                        lookupEnabled={lookupEnabled}
                        wordSpacing={entry.wordSpacing}
                      />
                    </span>
                  </span>
                ))}
              </span>
            </div>
          </li>
        )
      })}
    </ol>
  )
}

function CueText({
  cue,
  displayMode,
  lookupEnabled,
  wordSpacing,
}: {
  cue: CueSegment
  displayMode: WordTokenMode
  lookupEnabled: boolean
  wordSpacing: boolean
}) {
  if (cue.tokens.length === 0 || !lookupEnabled) {
    return <>{cue.text}</>
  }

  return (
    <>
      {cue.tokens.map((token, tokenIndex) => (
        <Fragment key={`${cue.id}-${tokenIndex}`}>
          {wordSpacing && tokenIndex > 0 ? ' ' : null}
          <WordToken token={token} displayMode={displayMode} />
        </Fragment>
      ))}
    </>
  )
}

function formatCueTime(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
