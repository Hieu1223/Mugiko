import { youtubeThumbnailUrl } from '../utils/video'

export function VideoThumbnail({ url, className }: { url: string; className?: string }) {
  const src = youtubeThumbnailUrl(url)
  if (!src) return null

  return (
    <img
      className={className ? `video-thumb ${className}` : 'video-thumb'}
      src={src}
      alt=""
      width={128}
      height={72}
      loading="lazy"
      decoding="async"
    />
  )
}
