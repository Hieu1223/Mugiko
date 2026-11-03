import { useEffect, useRef, useState } from 'react'
import { resolveYoutubeId } from '../utils/video'

interface VideoSurfaceProps {
  videoId?: string
  videoUrl: string
  startMs?: number
  onTime?: (ms: number) => void
  onDuration?: (ms: number) => void
  seekRef?: React.MutableRefObject<((ms: number) => void) | null>
}

declare global {
  interface Window {
    YT?: {
      Player: new (
        element: HTMLElement | string,
        options: {
          videoId: string
          playerVars?: Record<string, string | number>
          events?: {
            onReady?: () => void
            onStateChange?: (event: { data: number }) => void
            onError?: (event: { data: number }) => void
          }
        },
      ) => YouTubePlayer
    }
    onYouTubeIframeAPIReady?: () => void
  }
}

interface YouTubePlayer {
  getCurrentTime: () => number
  getDuration: () => number
  seekTo: (seconds: number, allowSeekAhead: boolean) => void
  playVideo: () => void
  pauseVideo: () => void
  destroy: () => void
}

let youtubeApiPromise: Promise<void> | null = null

/**
 * The IFrame API script's `load` event can fire before `YT.Player` exists,
 * and React StrictMode mounts effects twice. Wait for the actual constructor
 * (via the official callback plus polling) instead of resolving on `load`.
 */
function loadYouTubeApi(): Promise<void> {
  if (window.YT?.Player) return Promise.resolve()
  if (youtubeApiPromise) return youtubeApiPromise

  youtubeApiPromise = new Promise<void>((resolve, reject) => {
    let settled = false
    let pollTimer = 0
    let timeoutTimer = 0

    const cleanup = () => {
      window.clearInterval(pollTimer)
      window.clearTimeout(timeoutTimer)
    }

    const finish = () => {
      if (settled || !window.YT?.Player) return
      settled = true
      cleanup()
      resolve()
    }

    const fail = (message: string) => {
      if (settled) return
      settled = true
      cleanup()
      reject(new Error(message))
    }

    const previousReady = window.onYouTubeIframeAPIReady
    window.onYouTubeIframeAPIReady = () => {
      previousReady?.()
      finish()
    }

    pollTimer = window.setInterval(finish, 50)
    timeoutTimer = window.setTimeout(
      () => fail('YouTube player took too long to load.'),
      15000,
    )

    const existing = document.querySelector<HTMLScriptElement>('script[data-youtube-api]')
    if (existing) {
      existing.addEventListener('error', () => fail('YouTube API failed to load.'), {
        once: true,
      })
    } else {
      const script = document.createElement('script')
      script.src = 'https://www.youtube.com/iframe_api'
      script.async = true
      script.dataset.youtubeApi = 'true'
      script.addEventListener('error', () => fail('YouTube API failed to load.'), {
        once: true,
      })
      document.head.appendChild(script)
    }

    // Covers the case where the script was already loaded by a previous mount.
    finish()
  }).catch((error: unknown) => {
    youtubeApiPromise = null
    throw error
  })

  return youtubeApiPromise
}

export function VideoSurface({ videoId, videoUrl, startMs = 0, onTime, onDuration, seekRef }: VideoSurfaceProps) {
  const youtubeId = resolveYoutubeId(videoId, videoUrl)
  const containerRef = useRef<HTMLDivElement>(null)
  const playerRef = useRef<YouTubePlayer | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const startRef = useRef(startMs)
  startRef.current = startMs
  const [error, setError] = useState<string | null>(null)
  const [playbackError, setPlaybackError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  const [mounted, setMounted] = useState(false)
  const onTimeRef = useRef(onTime)
  onTimeRef.current = onTime
  const onDurationRef = useRef(onDuration)
  onDurationRef.current = onDuration

  useEffect(() => {
    if (!youtubeId || !containerRef.current) return
    let destroyed = false
    let mount: HTMLDivElement | null = null
    setError(null)
    setPlaybackError(null)
    setReady(false)
    setMounted(false)

    loadYouTubeApi()
      .then(() => {
        if (destroyed || !containerRef.current) return
        const yt = window.YT
        if (!yt?.Player) throw new Error('YouTube player API is unavailable.')
        // The iframe API replaces the element it is given, so use a child
        // that React does not own.
        mount = document.createElement('div')
        mount.className = 'video-surface__mount'
        containerRef.current.appendChild(mount)
        const player = new yt.Player(mount, {
          videoId: youtubeId,
          playerVars: {
            rel: 0,
            modestbranding: 1,
            playsinline: 1,
            start: Math.floor(startRef.current / 1000),
          },
          events: {
            onReady: () => {
              if (destroyed) return
              playerRef.current = player
              setReady(true)
              onDurationRef.current?.(player.getDuration() * 1000)
              if (startRef.current > 0) player.seekTo(startRef.current / 1000, true)
            },
            onStateChange: () => {
              if (destroyed) return
              onDurationRef.current?.(player.getDuration() * 1000)
            },
            onError: (event) => {
              if (destroyed) return
              setPlaybackError(
                event.data === 101 || event.data === 150
                  ? 'Embedding is disabled for this video.'
                  : event.data === 100
                    ? 'This video is unavailable.'
                    : 'The player could not start this video.',
              )
            },
          },
        })
        playerRef.current = player
        setMounted(true)
      })
      .catch((err: Error) => {
        console.error(err)
        if (!destroyed) setError('Player unavailable.')
      })

    const interval = window.setInterval(() => {
      const player = playerRef.current
      if (!player || typeof player.getCurrentTime !== 'function') return
      try {
        onTimeRef.current?.(player.getCurrentTime() * 1000)
      } catch {
        // player may not be ready yet
      }
    }, 120)

    return () => {
      destroyed = true
      window.clearInterval(interval)
      try {
        playerRef.current?.destroy()
      } catch {
        // ignore teardown errors
      }
      playerRef.current = null
      mount?.remove()
    }
    // Recreate only when the video changes; resume position is read through a ref.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [youtubeId])

  useEffect(() => {
    if (youtubeId && ready && startMs > 0) {
      playerRef.current?.seekTo(startMs / 1000, true)
    }
  }, [youtubeId, ready, startMs])

  useEffect(() => {
    if (seekRef) {
      seekRef.current = (ms: number) => {
        if (youtubeId) {
          playerRef.current?.seekTo(ms / 1000, true)
        } else if (videoRef.current) {
          videoRef.current.currentTime = ms / 1000
          void videoRef.current.play().catch(() => undefined)
        }
      }
    }
    return () => {
      if (seekRef) seekRef.current = null
    }
  }, [seekRef, youtubeId])

  useEffect(() => {
    if (!youtubeId && videoRef.current && startMs > 0) {
      const node = videoRef.current
      const onLoaded = () => {
        node.currentTime = startMs / 1000
      }
      if (node.readyState >= 1) onLoaded()
      else node.addEventListener('loadedmetadata', onLoaded, { once: true })
      return () => node.removeEventListener('loadedmetadata', onLoaded)
    }
    return undefined
  }, [youtubeId, startMs])

  if (youtubeId) {
    const fallbackStart = startMs > 0 ? `&start=${Math.floor(startMs / 1000)}` : ''
    return (
      <div className="video-surface video-surface--youtube">
        <div ref={containerRef} className="video-surface__iframe" />
        {error && (
          <iframe
            className="video-surface__fallback"
            src={`https://www.youtube.com/embed/${youtubeId}?rel=0${fallbackStart}`}
            title="Video player"
            allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          />
        )}
        {!ready && !error && !mounted && <div className="video-surface__overlay">Loading…</div>}
        {(error || playbackError) && (
          <div className="video-surface__notice">
            <span>{error || playbackError}</span>
            <a href={`https://www.youtube.com/watch?v=${youtubeId}`} target="_blank" rel="noreferrer noopener">
              Open on YouTube ↗
            </a>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="video-surface">
      <video
        ref={videoRef}
        src={videoUrl}
        controls
        playsInline
        preload="metadata"
        onTimeUpdate={(event) => onTimeRef.current?.(event.currentTarget.currentTime * 1000)}
        onLoadedMetadata={(event) => onDurationRef.current?.(event.currentTarget.duration * 1000)}
        onError={() => setError('The video file could not be loaded.')}
      />
      {error && <div className="video-surface__overlay video-surface__overlay--error">{error}</div>}
    </div>
  )
}
