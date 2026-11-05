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
  ErrorState,
  Link,
  LoadingState,
  useAsync,
  useDocumentTitle,
  useParams,
  useSession,
} from '@mugiko/common'
import {
  getAllSubtitleSegments,
  getSubtitle,
  getSubtitleState,
  streamSubtitleStatus,
  updateSubtitleState,
} from '../libs/subtitles'
import type { SubtitleStatus } from '../libs/types'
import { activeCueIndex, formatClock, toCues, useAutosave } from '../utils/cues'
import { displayVideoName } from '../utils/video'
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

  const cues = useMemo(() => toCues(segments.data?.items || []), [segments.data])
  const activeIndex = useMemo(() => activeCueIndex(cues, timeMs), [cues, timeMs])

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
      if (cues.length === 0) return
      const base = activeIndex >= 0 ? activeIndex : 0
      const next = Math.min(Math.max(base + direction, 0), cues.length - 1)
      seek(cues[next].startMs)
    },
    [cues, activeIndex, seek],
  )

  const goToIndex = useCallback(() => {
    const index = Number(gotoIndex) - 1
    if (!Number.isFinite(index) || cues.length === 0) return
    const clamped = Math.min(Math.max(Math.floor(index), 0), cues.length - 1)
    seek(cues[clamped].startMs)
    setGotoIndex('')
  }, [gotoIndex, cues, seek])

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
      <h1>{displayVideoName(data.video_url)}</h1>

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
            Go to #:{' '}
            <input
              type="number"
              min={1}
              max={Math.max(cues.length, 1)}
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
          <VideoSurface
            videoId={data.video_id}
            videoUrl={data.video_url}
            startMs={resumeMs}
            onTime={setTimeMs}
            onDuration={setDurationMs}
            seekRef={seekRef}
          />
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
                <SegmentList
                  cues={cues}
                  activeIndex={activeIndex}
                  autoScroll={prefs.autoScroll}
                  showTimestamps={prefs.showTimestamps}
                  displayMode={prefs.displayMode}
                  fontScale={prefs.fontScale}
                  lookupEnabled={prefs.lookupOnClick}
                  onSeek={seek}
                />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
