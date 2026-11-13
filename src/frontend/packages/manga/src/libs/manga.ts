import { apiFetch, type RequestOptions } from '@mugiko/common'
import type {
  ChapterDetail,
  ChapterListResponse,
  FilterListResponse,
  MangaDetail,
  MangaListResponse,
  MangaProviderDTO,
  TagListResponse,
} from './types'

let baseUrlCache: string | null = null
let providerPromise: Promise<string> | null = null

const PROVIDERS_PATH = '/manga/providers'

/**
 * Resolves the base URL of the default built-in manga provider from the
 * backend provider registry. Idempotent: the result is cached after the first
 * successful lookup so navigating between manga pages does not re-fetch it.
 *
 * On failure the cache is cleared so a subsequent call retries the lookup.
 *
 * All content calls go straight to the standalone manga server at this base
 * URL with `auth: false`, so no session token is sent cross-origin.
 */
async function resolveBaseUrl(signal?: AbortSignal): Promise<string> {
  if (baseUrlCache) return baseUrlCache
  if (!providerPromise) {
    providerPromise = (async () => {
      try {
        const providers = await apiFetch<MangaProviderDTO[]>(PROVIDERS_PATH, { signal, auth: true })
        const builtin = providers.find((provider) => provider.is_builtin && provider.base_url)
        if (!builtin) {
          throw new Error(
            'No built-in manga provider is configured on the backend. The manga server provider seed must run on startup.',
          )
        }
        baseUrlCache = builtin.base_url.replace(/\/+$/, '')
        return baseUrlCache
      } finally {
        providerPromise = null
      }
    })()
  }
  try {
    return await providerPromise
  } finally {
    // On rejection, clear so the next call retries. On success the cache is set.
  }
}

async function mangaFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const base = await resolveBaseUrl(options.signal)
  return apiFetch<T>(path, { ...options, base, auth: false })
}

export interface ListMangaParams {
  q?: string
  genre?: string
  author?: string
  artist?: string
  status?: string
  type?: string
  tags?: string
  sort?: string
  order?: string
  page?: number
  page_size?: number
}

export async function listManga(params: ListMangaParams = {}, signal?: AbortSignal): Promise<MangaListResponse> {
  return mangaFetch<MangaListResponse>('/api/v1/builtin-provider/manga', {
    query: params as RequestOptions['query'],
    signal,
  })
}

export async function getManga(idOrSlug: string, signal?: AbortSignal): Promise<MangaDetail> {
  return mangaFetch<MangaDetail>(
    `/api/v1/builtin-provider/manga/${encodeURIComponent(idOrSlug)}`,
    { signal },
  )
}

export async function listMangaChapters(
  mangaId: string,
  params: { page?: number; page_size?: number; sort?: string; order?: string } = {},
  signal?: AbortSignal,
): Promise<ChapterListResponse> {
  return mangaFetch<ChapterListResponse>(
    `/api/v1/builtin-provider/manga/${encodeURIComponent(mangaId)}/chapters`,
    { query: params as RequestOptions['query'], signal },
  )
}

export async function getChapter(chapterId: string, signal?: AbortSignal): Promise<ChapterDetail> {
  return mangaFetch<ChapterDetail>(
    `/api/v1/builtin-provider/chapters/${encodeURIComponent(chapterId)}`,
    { signal },
  )
}

export async function listTags(
  params: { category?: string; q?: string; page_size?: number } = {},
  signal?: AbortSignal,
): Promise<TagListResponse> {
  return mangaFetch<TagListResponse>('/api/v1/builtin-provider/tags', {
    query: params as RequestOptions['query'],
    signal,
  })
}

export async function listFilters(signal?: AbortSignal): Promise<FilterListResponse> {
  return mangaFetch<FilterListResponse>('/api/v1/builtin-provider/filters', { signal })
}

/** Test-only: clear the cached provider base URL. */
export function resetBuiltinProviderCacheForTests(): void {
  baseUrlCache = null
  providerPromise = null
}
