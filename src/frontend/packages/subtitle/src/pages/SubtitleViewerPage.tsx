import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react'
import {
  Button,
  ErrorState,
  Link,
  LoadingState,
  PageTitle,
  useAsync,
  useDocumentTitle,
  useParams,
  useSession,
} from '@mugiko/common'
import {
  getAllSubtitleSegments,
  getSubtitle,
  getSubtitleState,
  searchSubtitles,
  streamSubtitleStatus,
  updateSubtitleState,
} from '../libs/subtitles'
import type { SubtitleListItem, SubtitleStatus } from '../libs/types'
import {
  activeCueIndex,
  formatClock,
  mergeCueTracks,
  toCues,
  useAutosave,
  usesWordSpacing,
} from '../utils/cues'
import { displayVideoName } from '../utils/video'
import { CreateSubtitleDialog } from '../components/CreateSubtitleDialog'
import { SegmentList } from '../components/SegmentList'
import { VideoSurface } from '../components/VideoSurface'
import {
  DEFAULT_PLAYER_HEIGHT,
  DEFAULT_PLAYER_WIDTH,
  MAX_PLAYER_SIZE,
  MIN_PLAYER_SIZE,
  useSubtitlePreferences,
} from '../libs/preferences'

export function SubtitleViewerPage() {
  const { subtitleId = '' } = useParams()
  const { revision } = useSession()
  const [prefs, setPrefs] = useSubtitlePreferences()
  const [timeMs, setTimeMs] = useState(0)
  const [durationMs, setDurationMs] = useState(0)
  const [resumeMs, setResumeMs] = useState(0)
  const [resumeLoaded, setResumeLoaded] = useState(false)
  const [stateError, setStateError] = useState<string | null>(null)
  const [liveStatus, setLiveStatus] = useState<SubtitleStatus | null>(null)
  const [streamState, setStreamState] = useState<'idle' | 'live' | 'reconnecting'>('idle')
  const [gotoIndex, setGotoIndex] = useState('')
  const [secondaryId, setSecondaryId] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const seekRef = useRef<((ms: number) => void) | null>(null)
  const latestTime = useRef(0)
  latestTime.current = timeMs
  const areaRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{
    pointerId: number
    start: number
    baseSize: number
    currentSize: number
  } | null>(null)
  const [dragSize, setDragSize] = useState<number | null>(null)
  const [resizing, setResizing] = useState(false)

  const isStack = prefs.layout === 'stack-top' || prefs.layout === 'stack-bottom'
  const reversed = prefs.layout === 'side-right' || prefs.layout === 'stack-bottom'
  const storedPlayerSize = isStack ? prefs.playerHeight : prefs.playerWidth
  const playerSize = dragSize ?? storedPlayerSize

  useEffect(() => {
    if (!resizing) return
    const className = isStack ? 'watch-resizing--row' : 'watch-resizing--col'
    document.body.classList.add(className)
    return () => document.body.classList.remove(className)
  }, [resizing, isStack])

  useDocumentTitle('Subtitle viewer')

  // A viewer URL without a valid subtitle ID is a stale or malformed link.
  // Go back to the library instead of leaving e.g. `subtitleId=index.html`
  // in the address bar or requesting `/api/v1/subtitles/index.html`.
  useEffect(() => {
    if (!subtitleId) window.location.replace('/subtitle/')
  }, [subtitleId])

  useEffect(() => {
    document.body.classList.add('watch-page')
    return () => document.body.classList.remove('watch-page')
  }, [])

  const subtitle = useAsync((signal) => getSubtitle(subtitleId), [subtitleId, revision], {
    enabled: Boolean(subtitleId),
  })

  const status = liveStatus ?? subtitle.data?.status
  const isWorking = status === 'queued' || status === 'processing'
  const isFailed = status === 'failed' || (status as string | undefined) === 'error'

  // Keep the live status in sync when the subtitle detail is refetched.
  useEffect(() => {
    if (subtitle.data?.status) setLiveStatus(subtitle.data.status)
  }, [subtitle.data?.status])

  const segments = useAsync(
    (signal) => getAllSubtitleSegments(subtitleId, signal),
    [subtitleId, revision, status],
    { enabled: Boolean(subtitleId) && Boolean(subtitle.data) && !isWorking && !isFailed },
  )

  // Other completed tracks for the same video can be shown alongside this one.
  const candidates = useAsync(
    () => searchSubtitles({ video_url: subtitle.data?.video_url || '', limit: 50 }),
    [subtitle.data?.video_url, revision],
    { enabled: Boolean(subtitle.data?.video_url) },
  )

  const secondaryOptions = useMemo(
    () =>
      (candidates.data || []).filter(
        (item) => item.id !== subtitleId && (!item.status || item.status === 'completed'),
      ),
    [candidates.data, subtitleId],
  )

  useEffect(() => {
    if (secondaryId && !secondaryOptions.some((item) => item.id === secondaryId)) {
      setSecondaryId('')
    }
  }, [secondaryId, secondaryOptions])

  const secondaryLanguage = secondaryOptions.find((item) => item.id === secondaryId)?.language
  const secondarySegments = useAsync(
    (signal) => getAllSubtitleSegments(secondaryId, signal),
    [secondaryId, revision],
    { enabled: Boolean(secondaryId) },
  )

  // Follow worker status changes over SSE while the job is queued/processing.
  useEffect(() => {
    if (!subtitleId || !isWorking) {
      setStreamState('idle')
      return
    }

    const controller = new AbortController()
    let alive = true
    let retry = 0
    let timer: number | undefined

    const scheduleReconnect = () => {
      if (!alive) return
      setStreamState('reconnecting')
      const delay = Math.min(1000 * 2 ** retry, 15000)
      retry += 1
      timer = window.setTimeout(connect, delay)
    }

    const connect = () => {
      if (!alive) return
      setStreamState(retry === 0 ? 'live' : 'reconnecting')

      streamSubtitleStatus(
        subtitleId,
        (event) => {
          if (!alive) return
          retry = 0
          setStreamState('live')
          setLiveStatus(event.status)
          if (event.status === 'completed' || event.status === 'failed') {
            subtitle.reload()
          }
        },
        controller.signal,
      )
        .then(() => scheduleReconnect())
        .catch((err) => {
          if (!alive || controller.signal.aborted) return
          if (err instanceof DOMException && err.name === 'AbortError') return
          scheduleReconnect()
        })
    }

    connect()

    return () => {
      alive = false
      controller.abort()
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [subtitleId, isWorking, subtitle.reload])

  // Safety net: refresh the detail occasionally in case the stream is unavailable.
  useEffect(() => {
    if (!isWorking) return
    const timer = window.setInterval(() => subtitle.reload(), 20000)
    return () => window.clearInterval(timer)
  }, [isWorking, subtitle.reload])

  const cues = useMemo(
    () => toCues(segments.data?.items || [], subtitle.data?.language),
    [segments.data, subtitle.data?.language],
  )

  const secondaryCues = useMemo(
    () => toCues(secondarySegments.data?.items || [], secondaryLanguage),
    [secondarySegments.data, secondaryLanguage],
  )

  const lines = useMemo(
    () => mergeCueTracks(cues, secondaryId ? secondaryCues : []),
    [cues, secondaryCues, secondaryId],
  )
  const activeIndex = useMemo(() => activeCueIndex(lines, timeMs), [lines, timeMs])

  useEffect(() => {
    if (!subtitleId || resumeLoaded) return
    let alive = true
    getSubtitleState(subtitleId)
      .then((state) => {
        if (!alive) return
        const position = Number(state?.data?.position_ms)
        if (Number.isFinite(position) && position > 0) setResumeMs(position)
      })
      .catch(() => undefined)
      .finally(() => {
        if (alive) setResumeLoaded(true)
      })
    return () => {
      alive = false
    }
  }, [subtitleId, resumeLoaded])

  const persistState = useCallback(() => {
    const position = latestTime.current
    if (!subtitleId || position <= 0) return
    updateSubtitleState(subtitleId, { position_ms: Math.floor(position) }).catch((err) => {
      setStateError(err instanceof Error ? err.message : 'Position could not be saved.')
    })
  }, [subtitleId])

  useAutosave(persistState, Boolean(subtitleId) && timeMs > 0, 8000)
  useEffect(() => {
    const onBeforeUnload = () => persistState()
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [persistState])

  const seek = useCallback((ms: number) => {
    seekRef.current?.(ms)
    setTimeMs(ms)
  }, [])

  const jumpToCue = useCallback(
    (direction: 1 | -1) => {
      if (lines.length === 0) return
      const base = activeIndex >= 0 ? activeIndex : 0
      const next = Math.min(Math.max(base + direction, 0), lines.length - 1)
      seek(lines[next].startMs)
    },
    [lines, activeIndex, seek],
  )

  const goToIndex = useCallback(() => {
    const index = Number(gotoIndex) - 1
    if (!Number.isFinite(index) || lines.length === 0) return
    const clamped = Math.min(Math.max(Math.floor(index), 0), lines.length - 1)
    seek(lines[clamped].startMs)
    setGotoIndex('')
  }, [gotoIndex, lines, seek])

  const commitPlayerSize = useCallback(
    (next: number) => {
      const size = Math.round(next)
      setPrefs((current) =>
        isStack
          ? { ...current, playerHeight: size }
          : { ...current, playerWidth: size },
      )
    },
    [isStack, setPrefs],
  )

  const playerSizeLimit = useCallback(() => {
    const area = areaRef.current
    if (!area) return MAX_PLAYER_SIZE
    if (isStack) return Math.max(MIN_PLAYER_SIZE, area.clientHeight * 0.85)
    // Keep the 16:9 player from growing taller than the visible area.
    const byHeight = area.clientHeight * (16 / 9)
    return Math.max(
      MIN_PLAYER_SIZE,
      Math.min(area.clientWidth * 0.85, byHeight, MAX_PLAYER_SIZE),
    )
  }, [isStack])

  const startResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.pointerType === 'mouse' && event.button !== 0) return
    event.preventDefault()
    event.currentTarget.focus({ preventScroll: true })
    dragRef.current = {
      pointerId: event.pointerId,
      start: isStack ? event.clientY : event.clientX,
      baseSize: playerSize,
      currentSize: playerSize,
    }
    setDragSize(playerSize)
    setResizing(true)
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const moveResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    const delta = (isStack ? event.clientY : event.clientX) - drag.start
    const next = Math.round(
      Math.min(
        Math.max(drag.baseSize + (reversed ? -delta : delta), MIN_PLAYER_SIZE),
        playerSizeLimit(),
      ),
    )
    drag.currentSize = next
    setDragSize(next)
  }

  const endResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    dragRef.current = null
    commitPlayerSize(drag.currentSize)
    setDragSize(null)
    setResizing(false)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  const nudgeResize = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 64 : 16
    let delta = 0
    if (isStack) {
      if (event.key === 'ArrowUp') delta = -step
      else if (event.key === 'ArrowDown') delta = step
    } else {
      if (event.key === 'ArrowLeft') delta = -step
      else if (event.key === 'ArrowRight') delta = step
    }
    if (delta === 0) return
    event.preventDefault()
    const next = Math.min(
      Math.max(playerSize + (reversed ? -delta : delta), MIN_PLAYER_SIZE),
      playerSizeLimit(),
    )
    commitPlayerSize(next)
  }

  const resetPlayerSize = () => {
    commitPlayerSize(isStack ? DEFAULT_PLAYER_HEIGHT : DEFAULT_PLAYER_WIDTH)
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
      if (target?.closest('[data-lookup-layer]')) return
      if (target?.closest('[role="separator"]')) return
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        jumpToCue(1)
      } else if (event.key === 'ArrowUp') {
        event.preventDefault()
        jumpToCue(-1)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [jumpToCue])

  if (subtitle.loading && !subtitle.data) {
    return (
      <div className="page">
        <LoadingState label="Loading subtitle" />
      </div>
    )
  }

  if (!subtitle.data) {
    return (
      <div className="page">
        <h1>Subtitle</h1>
        <ErrorState
          message={subtitle.error || 'Subtitle not found.'}
          forbidden={subtitle.forbidden}
          onRetry={subtitle.reload}
        />
        <p>
          <Link to="/subtitle">← Subtitles</Link>
        </p>
      </div>
    )
  }

  const data = subtitle.data
  const areaStyle = { '--watch-player-size': `${playerSize}px` } as CSSProperties

  return (
    <div className="watch">
      <PageTitle
        title={displayVideoName(data.video_url)}
        actions={
          <Button variant="primary" onClick={() => setCreateOpen(true)}>
            New subtitle
          </Button>
        }
      />

      <details className="watch-controls" open>
        <summary>Controls</summary>
        <div className="watch-controls__body">
          <label>
            Display:{' '}
            <select
              value={prefs.displayMode}
              onChange={(event) =>
                setPrefs((current) => ({
                  ...current,
                  displayMode: event.target.value as typeof current.displayMode,
                }))
              }
            >
              <option value="normal">Normal</option>
              <option value="hiragana">Hiragana</option>
              <option value="both">Both (ruby)</option>
              <option value="reverse">Reverse (kanji on top)</option>
            </select>
          </label>
          <label>
            Layout:{' '}
            <select
              value={prefs.layout}
              onChange={(event) =>
                setPrefs((current) => ({
                  ...current,
                  layout: event.target.value as typeof current.layout,
                }))
              }
            >
              <option value="side-left">Video left</option>
              <option value="side-right">Video right</option>
              <option value="stack-top">Video top</option>
              <option value="stack-bottom">Video bottom</option>
            </select>
          </label>
          {secondaryOptions.length > 0 && (
            <label>
              Second subtitle:{' '}
              <select
                value={secondaryId}
                onChange={(event) => setSecondaryId(event.target.value)}
              >
                <option value="">Off</option>
                {secondaryOptions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {secondarySubtitleLabel(item)}
                  </option>
                ))}
              </select>
            </label>
          )}
          {secondaryId && (
            <label>
              Language order:{' '}
              <select
                value={prefs.dualOrder}
                onChange={(event) =>
                  setPrefs((current) => ({
                    ...current,
                    dualOrder: event.target.value as typeof current.dualOrder,
                  }))
                }
              >
                <option value="primary-first">Original first</option>
                <option value="secondary-first">Second first</option>
              </select>
            </label>
          )}
          <label>
            <input
              type="checkbox"
              checked={prefs.autoScroll}
              onChange={(event) =>
                setPrefs((current) => ({ ...current, autoScroll: event.target.checked }))
              }
            />{' '}
            Auto-scroll
          </label>
          <label>
            <input
              type="checkbox"
              checked={prefs.showTimestamps}
              onChange={(event) =>
                setPrefs((current) => ({ ...current, showTimestamps: event.target.checked }))
              }
            />{' '}
            Timestamps
          </label>
          <label>
            <input
              type="checkbox"
              checked={prefs.lookupOnClick}
              onChange={(event) =>
                setPrefs((current) => ({ ...current, lookupOnClick: event.target.checked }))
              }
            />{' '}
            Word lookup
          </label>
          <label>
            <input
              type="checkbox"
              checked={prefs.captionOnVideo}
              onChange={(event) =>
                setPrefs((current) => ({ ...current, captionOnVideo: event.target.checked }))
              }
            />{' '}
            Captions on video
          </label>
          <label>
            Go to #:{' '}
            <input
              type="number"
              min={1}
              max={Math.max(lines.length, 1)}
              value={gotoIndex}
              onChange={(event) => setGotoIndex(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') goToIndex()
              }}
              style={{ width: '5em' }}
            />{' '}
            <button type="button" onClick={goToIndex}>
              Go
            </button>
          </label>
          <span className="muted">
            {formatClock(timeMs)} / {durationMs ? formatClock(durationMs) : '—'}
          </span>
          {status && <span className="muted">Status: {status}</span>}
          {stateError && <span className="error">{stateError}</span>}
        </div>
      </details>

      <div
        ref={areaRef}
        className={`watch-area ${prefs.layout}${resizing ? ' is-resizing' : ''}`}
        style={areaStyle}
      >
        <div className="watch-player">
          <div className="watch-player__surface">
            <VideoSurface
              videoId={data.video_id}
              videoUrl={data.video_url}
              startMs={resumeMs}
              onTime={setTimeMs}
              onDuration={setDurationMs}
              seekRef={seekRef}
            />
            {prefs.captionOnVideo && !isWorking && !isFailed && (
              <div className="video-caption-overlay" aria-live="polite">
                {(() => {
                  const primaryCue = lines[activeIndex]?.primary
                  const secondaryCue = lines[activeIndex]?.secondary
                  const entries: Array<{ key: string; cue: typeof primaryCue; language?: string }> = []
                  if (primaryCue) entries.push({ key: 'primary', cue: primaryCue, language: data.language })
                  if (secondaryCue) entries.push({ key: 'secondary', cue: secondaryCue, language: secondaryLanguage })
                  if (prefs.dualOrder === 'secondary-first') entries.reverse()
                  return entries.map((entry) => {
                    if (!entry.cue) return null
                    return (
                      <span key={entry.key} className={`video-caption-overlay__line video-caption-overlay__line--${entry.key}`}>
                        {secondaryId && entry.language && (
                          <span className="video-caption-overlay__lang">{entry.language.toUpperCase()}</span>
                        )}
                        {entry.cue.text}
                      </span>
                    )
                  })
                })()}
              </div>
            )}
          </div>
        </div>

        <div
          className={`watch-resizer${resizing ? ' is-active' : ''}`}
          role="separator"
          aria-orientation={isStack ? 'horizontal' : 'vertical'}
          aria-label="Resize video and transcript"
          aria-valuemin={MIN_PLAYER_SIZE}
          aria-valuemax={MAX_PLAYER_SIZE}
          aria-valuenow={Math.round(playerSize)}
          title="Drag to resize. Double-click to reset."
          tabIndex={0}
          onPointerDown={startResize}
          onPointerMove={moveResize}
          onPointerUp={endResize}
          onPointerCancel={endResize}
          onLostPointerCapture={endResize}
          onDoubleClick={resetPlayerSize}
          onKeyDown={nudgeResize}
        />

        <div className="watch-subs">
          {isWorking && (
            <p className="status" role="status">
              {status === 'queued' ? 'Subtitle queued.' : 'Subtitle processing.'}{' '}
              {streamState === 'reconnecting'
                ? 'Reconnecting for live updates; the status also refreshes every 20 seconds.'
                : 'The transcript will appear here automatically when ready.'}
            </p>
          )}

          {isFailed && (
            <>
              <ErrorState message="Subtitle processing failed. Create it again with another provider, or try a different video." />
              <p>
                <Link to="/subtitle?create=1">Create another subtitle</Link>
              </p>
            </>
          )}

          {!isWorking && !isFailed && (
            <>
              {(segments.loading || (!segments.data && !segments.error)) && (
                <LoadingState label="Loading segments" />
              )}
              {segments.error && (
                <ErrorState
                  message={segments.error}
                  forbidden={segments.forbidden}
                  onRetry={segments.reload}
                />
              )}
              {!segments.loading && !segments.error && segments.data && (
                <>
                  <SegmentList
                    lines={lines}
                    activeIndex={activeIndex}
                    autoScroll={prefs.autoScroll}
                    showTimestamps={prefs.showTimestamps}
                    displayMode={prefs.displayMode}
                    fontScale={prefs.fontScale}
                    lookupEnabled={prefs.lookupOnClick}
                    order={prefs.dualOrder}
                    primaryLanguage={data.language}
                    secondaryLanguage={secondaryId ? secondaryLanguage : undefined}
                    primaryWordSpacing={usesWordSpacing(data.language)}
                    secondaryWordSpacing={usesWordSpacing(secondaryLanguage)}
                    onSeek={seek}
                  />
                  {secondaryId && secondarySegments.loading && (
                    <p className="status">Loading second subtitle…</p>
                  )}
                  {secondaryId && secondarySegments.error && (
                    <ErrorState
                      message={secondarySegments.error}
                      forbidden={secondarySegments.forbidden}
                      onRetry={secondarySegments.reload}
                    />
                  )}
                </>
              )}
            </>
          )}
        </div>
      </div>

      {createOpen && (
        <CreateSubtitleDialog
          initialVideoUrl={data.video_url}
          onClose={() => setCreateOpen(false)}
        />
      )}
    </div>
  )
}

function displayLanguage(language?: string): string {
  return language ? language.toUpperCase() : 'Unknown'
}

function secondarySubtitleLabel(item: SubtitleListItem): string {
  const language = displayLanguage(item.language)
  if (!item.created_at) return language
  const created = new Date(item.created_at)
  if (Number.isNaN(created.getTime())) return language
  return `${language} · ${created.toLocaleDateString()}`
}
