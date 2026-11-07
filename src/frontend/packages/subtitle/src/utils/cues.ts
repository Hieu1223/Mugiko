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

/** Languages whose words are separated by spaces in normal writing. */
const WORD_SPACED_LANGUAGES = new Set(['vi'])

export function usesWordSpacing(language?: string): boolean {
  if (!language) return false
  return WORD_SPACED_LANGUAGES.has(language.toLowerCase().split('-')[0])
}

/** Normalize the untyped segment payload into usable cues. */
export function toCues(
  items: Array<{ id: string; idx: number; start_ms: number; end_ms: number; words: unknown }>,
  language?: string,
): CueSegment[] {
  const separator = usesWordSpacing(language) ? ' ' : ''

  return items
    .map((item) => {
      const tokens = normalizeTokens(item.words)
      const rawText =
        typeof item.words === 'string'
          ? item.words
          : tokens.length > 0
            ? tokens.map((token) => token.text).join(separator)
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

export function activeCueIndex(
  items: ReadonlyArray<{ startMs: number; endMs: number }>,
  timeMs: number,
): number {
  let lastStarted = -1
  for (let index = 0; index < items.length; index += 1) {
    const item = items[index]
    if (item.startMs > timeMs) break
    lastStarted = index
    if (timeMs <= item.endMs) return index
  }
  // Keep the most recent line visible in the gap between lines.
  return lastStarted
}

/** One transcript row, potentially pairing the same moment in two languages. */
export interface SubtitleLine {
  id: string
  startMs: number
  endMs: number
  primary?: CueSegment
  secondary?: CueSegment
}

/**
 * Combine two cue tracks into a single list. Cues that overlap in time are
 * paired into one row so both languages render in the same list item.
 */
export function mergeCueTracks(
  primary: CueSegment[],
  secondary: CueSegment[] = [],
): SubtitleLine[] {
  const lines: SubtitleLine[] = []
  let primaryIndex = 0
  let secondaryIndex = 0

  while (primaryIndex < primary.length || secondaryIndex < secondary.length) {
    const primaryCue = primary[primaryIndex]
    const secondaryCue = secondary[secondaryIndex]

    if (primaryCue && secondaryCue) {
      const overlaps =
        Math.min(primaryCue.endMs, secondaryCue.endMs) >=
        Math.max(primaryCue.startMs, secondaryCue.startMs)
      if (overlaps) {
        lines.push({
          id: `${primaryCue.id}:${secondaryCue.id}`,
          startMs: Math.min(primaryCue.startMs, secondaryCue.startMs),
          endMs: Math.max(primaryCue.endMs, secondaryCue.endMs),
          primary: primaryCue,
          secondary: secondaryCue,
        })
        primaryIndex += 1
        secondaryIndex += 1
        continue
      }
      if (primaryCue.startMs <= secondaryCue.startMs) {
        lines.push(cueLine(primaryCue))
        primaryIndex += 1
      } else {
        lines.push(cueLine(secondaryCue))
        secondaryIndex += 1
      }
      continue
    }

    if (primaryCue) {
      lines.push(cueLine(primaryCue))
      primaryIndex += 1
    } else if (secondaryCue) {
      lines.push(cueLine(secondaryCue))
      secondaryIndex += 1
    }
  }

  return lines
}

function cueLine(cue: CueSegment): SubtitleLine {
  return {
    id: cue.id,
    startMs: cue.startMs,
    endMs: cue.endMs,
    primary: cue,
  }
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
