import { useEffect, useRef, useState } from 'react'
import { parseVideoUrl } from '../utils/video'

interface VideoPreviewProps {
  url: string
  title?: string
  className?: string
  compact?: boolean
}

export function VideoPreview({ url, title = 'Preview', className, compact }: VideoPreviewProps) {
  const source = parseVideoUrl(url)
  const [videoReady, setVideoReady] = useState(false)
  const [videoFailed, setVideoFailed] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    setVideoReady(false)
    setVideoFailed(false)
  }, [url])

  return (
    <figure className={`video-preview ${className || ''}`}>
      {!compact && (
        <div className="video-preview__bar">
          <span>{title}</span>
          <span className="muted">
            {source.kind === 'youtube' ? 'YouTube' : source.kind === 'file' ? 'Video' : ''}
          </span>
        </div>
      )}

      <div className="video-preview__stage">
        {source.kind === 'youtube' && (
          <iframe
            key={source.videoId}
            src={source.embedUrl}
            title="Video preview"
            allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
            loading="lazy"
            referrerPolicy="strict-origin-when-cross-origin"
          />
        )}

        {source.kind === 'file' && (
          <video
            ref={videoRef}
            key={source.url}
            src={source.url}
            controls
            preload="metadata"
            playsInline
            onLoadedData={() => setVideoReady(true)}
            onError={() => setVideoFailed(true)}
          />
        )}

        {(source.kind === 'unsupported' || videoFailed) && (
          <div className="video-preview__placeholder">
            <span>{source.kind === 'unsupported' ? 'No preview.' : 'Video could not load.'}</span>
            {source.kind === 'unsupported' && url.trim() && (
              <a href={source.url} target="_blank" rel="noreferrer noopener">
                Open source
              </a>
            )}
          </div>
        )}
      </div>

      {!compact && source.kind === 'file' && (
        <figcaption className="video-preview__foot">
          <span className="muted">{videoReady ? 'Ready' : videoFailed ? 'Error' : 'Loading…'}</span>
        </figcaption>
      )}
    </figure>
  )
}
