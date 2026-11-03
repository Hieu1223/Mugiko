import { useEffect, useRef, useState } from 'react'
import { normalizeTokens, type RenderToken } from '@mugiko/common'

export interface CueSegment {
  id: string
  idx: number
  startMs: number
  endMs: number
  tokens: RenderToken[]
  text: string
}

/** Normalize the untyped segment payload into usable cues. */
export function toCues(
  items: Array<{ id: string; idx: number; start_ms: number; end_ms: number; words: unknown }>,
): CueSegment[] {
  return items
    .map((item) => {
      const tokens = normalizeTokens(item.words)
      const rawText =
        typeof item.words === 'string'
          ? item.words
          : tokens.length > 0
            ? tokens.map((token) => token.text).join('')
            : ''
      return {
        id: item.id,
        idx: item.idx,
        startMs: Number(item.start_ms) || 0,
        endMs: Number(item.end_ms) || 0,
        tokens,
        text: rawText.trim(),
      }
    })
    .filter((cue) => cue.text.length > 0)
    .sort((a, b) => a.startMs - b.startMs)
}

export function activeCueIndex(cues: CueSegment[], timeMs: number): number {
  if (cues.length === 0) return -1
  let low = 0
  let high = cues.length - 1
  let result = -1
  while (low <= high) {
    const mid = (low + high) >> 1
    const cue = cues[mid]
    if (timeMs < cue.startMs) {
      high = mid - 1
    } else if (timeMs > cue.endMs) {
      low = mid + 1
    } else {
      result = mid
      break
    }
  }
  if (result === -1) {
    // Keep the most recent cue visible in the gap between lines.
    for (let index = cues.length - 1; index >= 0; index -= 1) {
      if (cues[index].startMs <= timeMs) return index
    }
  }
  return result
}

export function formatClock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches,
  )
  useEffect(() => {
    const media = window.matchMedia(query)
    const onChange = () => setMatches(media.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [query])
  return matches
}

export function useAutosave(callback: () => void, enabled: boolean, intervalMs = 5000) {
  const saved = useRef(callback)
  saved.current = callback
  useEffect(() => {
    if (!enabled) return
    const timer = window.setInterval(() => saved.current(), intervalMs)
    return () => window.clearInterval(timer)
  }, [enabled, intervalMs])
}
