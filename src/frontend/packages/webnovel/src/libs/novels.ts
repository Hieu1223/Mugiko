import { apiFetch } from '@mugiko/common'
import type {
  AddNovelResponse,
  ChapterWithParagraphs,
  NovelSearchResponse,
  NovelWithChapters,
  PaginatedNovels,
  PreviewResponse,
} from './types'

export async function listNovels(page = 1, pageSize = 20): Promise<PaginatedNovels> {
  return apiFetch<PaginatedNovels>('/webnovel/novels', { query: { page, page_size: pageSize } })
}

export async function listAllNovels(page = 1, pageSize = 20): Promise<PaginatedNovels> {
  return apiFetch<PaginatedNovels>('/webnovel/novels/all', {
    query: { page, page_size: pageSize },
  })
}

export async function getNovel(id: string): Promise<NovelWithChapters> {
  return apiFetch<NovelWithChapters>(`/webnovel/novels/${id}`)
}

export async function previewNovel(url: string): Promise<PreviewResponse> {
  return apiFetch<PreviewResponse>('/webnovel/preview', { method: 'POST', body: { url } })
}

export async function addNovel(url: string): Promise<AddNovelResponse> {
  return apiFetch<AddNovelResponse>('/webnovel/novels', { method: 'POST', body: { url } })
}

export async function searchNovels(query: string, limit = 30): Promise<NovelSearchResponse> {
  return apiFetch<NovelSearchResponse>('/webnovel/search', {
    method: 'POST',
    body: { query, limit },
  })
}

export async function getChapter(id: string): Promise<ChapterWithParagraphs> {
  return apiFetch<ChapterWithParagraphs>(`/webnovel/chapters/${id}`)
}

export async function syncNovel(force = false): Promise<unknown> {
  return apiFetch('/webnovel/sync', { method: 'POST', body: { force } })
}
