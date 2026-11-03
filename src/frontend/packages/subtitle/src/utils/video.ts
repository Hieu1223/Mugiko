export type VideoSource =
  | { kind: 'youtube'; videoId: string; embedUrl: string; watchUrl: string }
  | { kind: 'file'; url: string }
  | { kind: 'unsupported'; url: string }

const YOUTUBE_HOSTS = new Set([
  'youtube.com',
  'www.youtube.com',
  'm.youtube.com',
  'music.youtube.com',
  'youtu.be',
  'www.youtu.be',
  'youtube-nocookie.com',
  'www.youtube-nocookie.com',
])

const FILE_EXTENSION = /\.(mp4|webm|ogg|ogv|mov|m4v)(\?|#|$)/i

function youtubeIdFromUrl(url: URL): string | null {
  const host = url.hostname.toLowerCase()
  if (!YOUTUBE_HOSTS.has(host)) return null

  if (host.endsWith('youtu.be')) {
    const id = url.pathname.split('/').filter(Boolean)[0]
    return id || null
  }

  const queryId = url.searchParams.get('v')
  if (queryId) return queryId

  const parts = url.pathname.split('/').filter(Boolean)
  if (parts.length >= 2) {
    const [prefix, id] = parts
    if (['embed', 'shorts', 'live', 'v'].includes(prefix) && id) return id
  }
  return null
}

export function parseVideoUrl(raw: string): VideoSource {
  const url = raw.trim()
  if (!url) return { kind: 'unsupported', url: '' }

  try {
    const isRelative = url.startsWith('/') || url.startsWith('./') || url.startsWith('../')
    const parsed = new URL(url, isRelative ? window.location.origin : undefined)
    const youtubeId = youtubeIdFromUrl(parsed)
    if (youtubeId) {
      const safeId = encodeURIComponent(youtubeId)
      return {
        kind: 'youtube',
        videoId: youtubeId,
        embedUrl: `https://www.youtube-nocookie.com/embed/${safeId}?rel=0&modestbranding=1&enablejsapi=1&origin=${encodeURIComponent(window.location.origin)}`,
        watchUrl: `https://www.youtube.com/watch?v=${safeId}`,
      }
    }
    if (FILE_EXTENSION.test(parsed.pathname) || parsed.protocol === 'blob:') {
      return { kind: 'file', url }
    }
    if (parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1') {
      return { kind: 'file', url }
    }
    return { kind: 'unsupported', url }
  } catch {
    return { kind: 'unsupported', url }
  }
}

export function isLikelyVideoUrl(raw: string): boolean {
  return parseVideoUrl(raw).kind !== 'unsupported'
}

export function displayVideoName(url: string): string {
  try {
    const parsed = new URL(url)
    if (youtubeIdFromUrl(parsed)) {
      return `YouTube · ${youtubeIdFromUrl(parsed)}`
    }
    const name = parsed.pathname.split('/').filter(Boolean).pop()
    return name || parsed.hostname
  } catch {
    return url
  }
}

/** 16:9 thumbnail for YouTube videos; null for other video sources. */
export function youtubeThumbnailUrl(raw: string): string | null {
  const source = parseVideoUrl(raw)
  if (source.kind !== 'youtube') return null
  return `https://i.ytimg.com/vi/${encodeURIComponent(source.videoId)}/mqdefault.jpg`
}

export function resolveYoutubeId(videoId: string | undefined, videoUrl: string): string | null {
  const source = parseVideoUrl(videoUrl)
  return source.kind === 'youtube' ? source.videoId : null
}
