export type ProviderKind = 'remote' | 'youtube'

/** Worker-side job lifecycle from the subtitle queue. */
export type SubtitleStatus = 'queued' | 'processing' | 'completed' | 'failed'

/** One status update from the subtitle SSE stream. */
export interface SubtitleStatusEvent {
  subtitle_id: string
  status: SubtitleStatus
}

/** One tokenized subtitle word. */
export interface SubtitleWord {
  surface: string
  hiragana: string
}

export interface SubtitleProviderService {
  id: string
  provider_id: string
  service_key: string
  name: string
  options?: Record<string, unknown>
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface SubtitleProvider {
  id: string
  name: string
  kind: ProviderKind
  base_url?: string
  is_active?: boolean
  last_synced_at?: string | null
  created_at?: string
  updated_at?: string
  services?: SubtitleProviderService[]
}

export interface Subtitle {
  id: string
  video_id?: string
  video_url: string
  provider_id: string
  service_id?: string
  created_by?: string
  status?: SubtitleStatus
  language?: string
  created_at?: string
  updated_at?: string
}

export interface SubtitleListItem {
  id: string
  video_id?: string
  video_url: string
  provider_id: string
  service_id?: string
  created_by?: string
  created_at?: string
  status?: SubtitleStatus
  language?: string
  segment_count?: number
}

export interface SubtitleSegment {
  id: string
  subtitle_id?: string
  idx: number
  start_ms: number
  end_ms: number
  /** New API: `{ surface, hiragana }` entries. Normalized defensively at render time. */
  words: SubtitleWord[] | string | null
}

export interface SubtitleSegmentsResponse {
  items: SubtitleSegment[]
  total: number
  limit: number
  offset: number
}

export interface SubtitleHistoryItem {
  subtitle_id: string
  video_id?: string
  video_url: string
  language?: string
  last_accessed_at?: string
  segment_count?: number
}

export interface SubtitleHistoryResponse {
  items: SubtitleHistoryItem[]
  total: number
  limit: number
  offset: number
}

export interface SubtitleUserState {
  user_id?: string
  subtitle_id?: string
  schema_version: number
  data: Record<string, unknown>
  updated_at?: string
}

export interface SubtitleSettings {
  user_id?: string
  schema_version: number
  data: Record<string, unknown>
  updated_at?: string
}
