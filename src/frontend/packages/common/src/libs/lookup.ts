import { apiFetch } from './api'
import type {
  DictionaryEntry,
  KanjiEntry,
  PrefixSearchResponse,
} from './types'

export async function lookupWord(word: string, signal?: AbortSignal): Promise<DictionaryEntry> {
  return apiFetch<DictionaryEntry>('/lookup/word', { query: { word }, signal })
}

export async function lookupKanji(kanji: string, signal?: AbortSignal): Promise<KanjiEntry> {
  return apiFetch<KanjiEntry>('/lookup/kanji', { query: { kanji }, signal })
}

export async function lookupPrefix(
  prefix: string,
  limit = 50,
  signal?: AbortSignal,
): Promise<PrefixSearchResponse> {
  return apiFetch<PrefixSearchResponse>('/lookup/prefix', {
    query: { prefix, limit },
    signal,
  })
}

/** Trim the query back to a shorter prefix until something matches. */
export async function prefixWithFallback(
  query: string,
  signal?: AbortSignal,
): Promise<{ results: string[]; usedPrefix: string }> {
  const cleaned = query.trim()
  if (!cleaned) return { results: [], usedPrefix: '' }

  let candidate = cleaned
  while (candidate.length > 0) {
    const response = await lookupPrefix(candidate, 50, signal)
    const results = Array.isArray(response.results) ? response.results : []
    if (results.length > 0) return { results, usedPrefix: candidate }
    candidate = candidate.slice(0, -1)
  }
  return { results: [], usedPrefix: cleaned }
}
