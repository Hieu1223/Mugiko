import { apiFetch, apiRequest, streamServerEvents } from '@mugiko/common'
import type {
  Subtitle,
  SubtitleHistoryResponse,
  SubtitleListItem,
  SubtitleProvider,
  SubtitleSegmentsResponse,
  SubtitleSettings,
  SubtitleStatusEvent,
  SubtitleUserState,
} from './types'

export async function listSubtitleProviders(): Promise<SubtitleProvider[]> {
  return apiFetch<SubtitleProvider[]>('/subtitle-providers')
}

export async function createSubtitleProvider(input: {
  name: string
  kind: 'remote' | 'youtube'
  base_url?: string
}): Promise<SubtitleProvider> {
  return apiFetch<SubtitleProvider>('/subtitle-providers', { method: 'POST', body: input })
}

export interface SubtitleSearchParams {
  video_url?: string
  provider_id?: string
  limit?: number
  offset?: number
}

/**
 * The OpenAPI schema describes a single object, but the endpoint is a search.
 * Normalize an array, an { items } wrapper, or a single result.
 */
export async function searchSubtitles(params: SubtitleSearchParams): Promise<SubtitleListItem[]> {
  const result = await apiRequest<unknown>('/subtitles', { query: { ...params } })
  return normalizeSubtitleList(result.data)
}

export function normalizeSubtitleList(payload: unknown): SubtitleListItem[] {
  if (!payload) return []
  if (Array.isArray(payload)) return payload.filter(isSubtitleItem)
  if (typeof payload === 'object') {
    const record = payload as Record<string, unknown>
    for (const key of ['items', 'subtitles', 'results']) {
      if (Array.isArray(record[key])) return (record[key] as unknown[]).filter(isSubtitleItem)
    }
    if (isSubtitleItem(payload)) return [payload]
  }
  return []
}

function isSubtitleItem(value: unknown): value is SubtitleListItem {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return typeof record.id === 'string' && typeof record.video_url === 'string'
}

export async function createSubtitle(input: {
  video_url: string
  provider_id: string
  service_key: string
}): Promise<Subtitle> {
  return apiFetch<Subtitle>('/subtitles', { method: 'POST', body: input })
}

export async function getSubtitle(id: string): Promise<Subtitle> {
  return apiFetch<Subtitle>(`/subtitles/${id}`)
}

/**
 * Follow subtitle status changes until the worker reaches a terminal status.
 * The server closes the stream after `completed` or `failed`.
 */
export async function streamSubtitleStatus(
  id: string,
  onStatus: (event: SubtitleStatusEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  await streamServerEvents(`/subtitles/${id}/status`, { signal }, (event) => {
    if (event.event !== 'status') return
    const parsed = parseStatusEvent<SubtitleStatusEvent>(event.data)
    if (parsed) onStatus(parsed)
  })
}

function parseStatusEvent<T>(data: string): T | null {
  try {
    return JSON.parse(data) as T
  } catch {
    return null
  }
}

export async function getSubtitleSegments(
  id: string,
  limit = 100,
  offset = 0,
): Promise<SubtitleSegmentsResponse> {
  return apiFetch<SubtitleSegmentsResponse>(`/subtitles/${id}/segments`, {
    query: { limit, offset },
  })
}

export async function getAllSubtitleSegments(
  id: string,
  signal?: AbortSignal,
): Promise<SubtitleSegmentsResponse> {
  const pageSize = 200
  const first = await apiFetch<SubtitleSegmentsResponse>(`/subtitles/${id}/segments`, {
    query: { limit: pageSize, offset: 0 },
    signal,
  })
  const items = Array.isArray(first.items) ? [...first.items] : []
  const total = first.total ?? items.length
  let guard = 0

  while (items.length < total && guard < 50) {
    guard += 1
    const next = await apiFetch<SubtitleSegmentsResponse>(`/subtitles/${id}/segments`, {
      query: { limit: pageSize, offset: items.length },
      signal,
    })
    const chunk = Array.isArray(next.items) ? next.items : []
    if (chunk.length === 0) break
    const alreadySeen = chunk.some((item) => items.some((existing) => existing.id === item.id))
    if (alreadySeen) break
    items.push(...chunk)
  }

  return { ...first, items, total }
}

export async function getSubtitleHistory(limit = 20, offset = 0): Promise<SubtitleHistoryResponse> {
  return apiFetch<SubtitleHistoryResponse>('/users/me/subtitle-history', {
    query: { limit, offset },
  })
}

export async function getSubtitleSettings(): Promise<SubtitleSettings> {
  return apiFetch<SubtitleSettings>('/users/me/subtitle-settings')
}

export async function updateSubtitleSettings(
  schemaVersion: number,
  data: Record<string, unknown>,
): Promise<SubtitleSettings> {
  return apiFetch<SubtitleSettings>('/users/me/subtitle-settings', {
    method: 'PUT',
    body: { schema_version: schemaVersion, data },
  })
}

export async function getSubtitleState(id: string): Promise<SubtitleUserState | null> {
  try {
    return await apiFetch<SubtitleUserState>(`/subtitles/${id}/state`)
  } catch {
    return null
  }
}

export async function updateSubtitleState(
  id: string,
  data: Record<string, unknown>,
): Promise<SubtitleUserState | null> {
  try {
    return await apiFetch<SubtitleUserState>(`/subtitles/${id}/state`, {
      method: 'PUT',
      body: { schema_version: 1, data },
    })
  } catch {
    return null
  }
}
