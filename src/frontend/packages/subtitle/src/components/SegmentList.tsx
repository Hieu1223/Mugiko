import { useEffect, useRef } from 'react'
import { WordToken, type WordTokenMode } from '@mugiko/common'
import type { CueSegment } from '../utils/cues'

interface SegmentListProps {
  cues: CueSegment[]
  activeIndex: number
  autoScroll: boolean
  showTimestamps: boolean
  displayMode: WordTokenMode
  fontScale: number
  lookupEnabled: boolean
  onSeek: (ms: number) => void
}

export function SegmentList({
  cues,
  activeIndex,
  autoScroll,
  showTimestamps,
  displayMode,
  fontScale,
  lookupEnabled,
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

  if (cues.length === 0) {
    return <p className="status">No segments.</p>
  }

  return (
    <ol className="segment-list" ref={listRef}>
      {cues.map((cue, index) => {
        const isActive = index === activeIndex
        return (
          <li
            key={cue.id}
            data-cue-index={index}
            className={`segment ${isActive ? 'is-active' : ''}`}
            onClick={() => onSeek(cue.startMs)}
          >
            <button
              type="button"
              className="segment__time"
              onClick={(event) => {
                event.stopPropagation()
                onSeek(cue.startMs)
              }}
            >
              {String(index + 1).padStart(3, '0')}{' '}
              {showTimestamps ? formatCueTime(cue.startMs) : ''}
            </button>
            <span className="segment__text" style={{ fontSize: `${0.98 * fontScale}em` }}>
              {cue.tokens.length > 0 ? (
                lookupEnabled ? (
                  cue.tokens.map((token, tokenIndex) => (
                    <WordToken
                      key={`${cue.id}-${tokenIndex}`}
                      token={token}
                      displayMode={displayMode}
                    />
                  ))
                ) : (
                  cue.text
                )
              ) : (
                cue.text
              )}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function formatCueTime(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}
