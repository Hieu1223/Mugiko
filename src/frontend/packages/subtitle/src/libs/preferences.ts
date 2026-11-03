import { useEffect, useState } from 'react'

export type SubtitleDisplayMode = 'normal' | 'hiragana' | 'both' | 'reverse'
export type SubtitleLayout = 'side-left' | 'side-right' | 'stack-top' | 'stack-bottom'

export interface SubtitlePreferences {
  fontScale: number
  autoScroll: boolean
  showTimestamps: boolean
  lookupOnClick: boolean
  displayMode: SubtitleDisplayMode
  layout: SubtitleLayout
  /** Player width in pixels for side-by-side layouts. */
  playerWidth: number
  /** Player height in pixels for stacked layouts. */
  playerHeight: number
}

const STORAGE_KEY = 'mugiko.subtitle.prefs'

export const MIN_PLAYER_SIZE = 160
export const MAX_PLAYER_SIZE = 4000

export const DEFAULT_PLAYER_WIDTH = 480
export const DEFAULT_PLAYER_HEIGHT = 320

const DEFAULTS: SubtitlePreferences = {
  fontScale: 1,
  autoScroll: true,
  showTimestamps: true,
  lookupOnClick: true,
  displayMode: 'both',
  layout: 'side-left',
  playerWidth: DEFAULT_PLAYER_WIDTH,
  playerHeight: DEFAULT_PLAYER_HEIGHT,
}

function clampPlayerSize(value: unknown, fallback: number): number {
  const size = Number(value)
  if (!Number.isFinite(size)) return fallback
  return Math.min(Math.max(size, MIN_PLAYER_SIZE), MAX_PLAYER_SIZE)
}

export function readSubtitlePreferences(): SubtitlePreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULTS
    const parsed = JSON.parse(raw) as Partial<SubtitlePreferences>
    return {
      ...DEFAULTS,
      ...parsed,
      playerWidth: clampPlayerSize(parsed.playerWidth, DEFAULTS.playerWidth),
      playerHeight: clampPlayerSize(parsed.playerHeight, DEFAULTS.playerHeight),
    }
  } catch {
    return DEFAULTS
  }
}

export function writeSubtitlePreferences(prefs: SubtitlePreferences) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
  } catch {
    // ignore
  }
}

export function useSubtitlePreferences() {
  const [prefs, setPrefs] = useState<SubtitlePreferences>(readSubtitlePreferences)

  useEffect(() => {
    writeSubtitlePreferences(prefs)
  }, [prefs])

  return [prefs, setPrefs] as const
}
