import { apiFetch } from './api'
import type {
  Deck,
  DeckWord,
  PaginatedDecks,
  PaginatedDeckWords,
} from './types'

export async function listDecks(page = 1, pageSize = 20): Promise<PaginatedDecks> {
  return apiFetch<PaginatedDecks>('/decks', { query: { page, page_size: pageSize } })
}

export async function getDeck(id: string): Promise<Deck> {
  return apiFetch<Deck>(`/decks/${id}`)
}

export async function listAllDecks(): Promise<Deck[]> {
  const first = await listDecks(1, 100)
  return Array.isArray(first.decks) ? first.decks : []
}

export async function createDeck(name: string): Promise<Deck> {
  return apiFetch<Deck>('/decks', { method: 'POST', body: { name } })
}

export async function renameDeck(id: string, name: string): Promise<Deck> {
  return apiFetch<Deck>(`/decks/${id}`, { method: 'PATCH', body: { name } })
}

export async function deleteDeck(id: string): Promise<void> {
  await apiFetch<void>(`/decks/${id}`, { method: 'DELETE' })
}

export async function listDeckWords(
  deckId: string,
  page = 1,
  pageSize = 20,
): Promise<PaginatedDeckWords> {
  return apiFetch<PaginatedDeckWords>(`/decks/${deckId}/words`, {
    query: { page, page_size: pageSize },
  })
}

export async function addDeckWord(
  deckId: string,
  word: string,
  meaning: string,
): Promise<DeckWord> {
  return apiFetch<DeckWord>(`/decks/${deckId}/words`, {
    method: 'POST',
    body: { word, meaning },
  })
}

export async function updateDeckWord(
  deckId: string,
  wordId: string,
  input: { word?: string; meaning?: string },
): Promise<DeckWord> {
  return apiFetch<DeckWord>(`/decks/${deckId}/words/${wordId}`, {
    method: 'PATCH',
    body: input,
  })
}

export async function deleteDeckWord(deckId: string, wordId: string): Promise<void> {
  await apiFetch<void>(`/decks/${deckId}/words/${wordId}`, { method: 'DELETE' })
}
