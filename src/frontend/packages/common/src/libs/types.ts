export type Role = 'anonymous' | 'user' | 'admin'
export type AuthType = 'firebase' | 'admin' | 'anonymous'

export interface UserProfile {
  user_id: string
  name?: string
  bio?: string
  email?: string
  role: Role
  joined_at?: string
  auth_type?: AuthType
  auth_id?: string
}

export interface Deck {
  id: string
  owner_id?: string
  name: string
  created_at?: string
  updated_at?: string
}

export interface DeckWord {
  id: string
  deck_id?: string
  word: string
  meaning: string
  created_at?: string
  updated_at?: string
}

export interface PaginatedDecks {
  decks: Deck[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface PaginatedDeckWords {
  words: DeckWord[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface DictionaryReading {
  kana: string
  meaning: string
}

export interface DictionaryEntry {
  word: string
  readings: DictionaryReading[]
}

export interface KanjiEntry {
  kanji: string
  reading: string
  meanings: string
  strokes: number
  radical: string
  penstrokes: string
  shape: string
  unicode: string
}

export interface PrefixSearchResponse {
  results: string[]
  limit: number
}

export interface HealthResponse {
  status: string
}
