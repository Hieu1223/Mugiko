import { useEffect, useState } from 'react'
import type { NovelReaderSettings } from './types'

const STORAGE_KEY = 'mugiko.webnovel.reader'

const DEFAULTS: NovelReaderSettings = {
  fontScale: 1,
  lineHeight: 1.9,
  widthPercent: 100,
  showFurigana: false,
}

export function readReaderSettings(): NovelReaderSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULTS
    return { ...DEFAULTS, ...(JSON.parse(raw) as Partial<NovelReaderSettings>) }
  } catch {
    return DEFAULTS
  }
}

export function writeReaderSettings(settings: NovelReaderSettings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // ignore
  }
}

export function useReaderSettings() {
  const [settings, setSettings] = useState<NovelReaderSettings>(readReaderSettings)

  useEffect(() => {
    writeReaderSettings(settings)
  }, [settings])

  return [settings, setSettings] as const
}

export interface ReadingPosition {
  chapterId: string
  chapterTitle?: string
  chapterIdx?: number
  updatedAt: number
}

const POSITION_KEY = 'mugiko.webnovel.positions'

function readPositions(): Record<string, ReadingPosition> {
  try {
    return JSON.parse(localStorage.getItem(POSITION_KEY) || '{}') as Record<string, ReadingPosition>
  } catch {
    return {}
  }
}

export function rememberPosition(novelId: string, position: ReadingPosition) {
  try {
    const positions = readPositions()
    positions[novelId] = position
    localStorage.setItem(POSITION_KEY, JSON.stringify(positions))
  } catch {
    // ignore
  }
}

export function getRememberedPosition(novelId: string): ReadingPosition | null {
  return readPositions()[novelId] || null
}
