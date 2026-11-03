export interface RenderToken {
  text: string
  lookup: string
  reading?: string
}

type UnknownRecord = Record<string, unknown>

function asRecord(value: unknown): UnknownRecord | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as UnknownRecord) : null
}

function stringField(record: UnknownRecord, keys: string[]): string | undefined {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  return undefined
}

function tokenFromUnknown(value: unknown): RenderToken | null {
  if (typeof value === 'string') {
    const text = value.trim()
    return text ? { text, lookup: text } : null
  }
  const record = asRecord(value)
  if (!record) return null
  const surface =
    stringField(record, ['surface', 'utf8', 'text', 'token', 'word', 'original', 'display']) || ''
  const base =
    stringField(record, ['base', 'dictionary_form', 'lemma', 'lookup', 'base_form', 'dictionary']) ||
    surface
  if (!base) return null
  return {
    text: surface || base,
    lookup: base,
    reading: stringField(record, ['hiragana', 'reading', 'kana', 'furigana']),
  }
}

function tokenListFrom(value: unknown): unknown[] | null {
  if (Array.isArray(value)) return value
  const record = asRecord(value)
  if (!record) return null
  for (const key of ['tokens', 'items', 'words', 'segments', 'data']) {
    const nested = record[key]
    if (Array.isArray(nested)) return nested
  }
  return null
}

/**
 * Normalizes the untyped `words` payload used by subtitle segments and novel
 * paragraphs. Handles arrays of strings, token objects, and wrappers. Plain
 * text is intentionally not tokenized, so a missing token stream stays
 * readable but non-clickable.
 */
export function normalizeTokens(value: unknown): RenderToken[] {
  const list = tokenListFrom(value)
  if (list) {
    return list.map(tokenFromUnknown).filter((token): token is RenderToken => Boolean(token))
  }

  const single = tokenFromUnknown(value)
  if (single && typeof value !== 'string') return [single]

  return []
}

/** Render tokens as inline text, keeping whitespace/punctuation between tokens. */
export function tokensToParts(tokens: RenderToken[]): RenderToken[] {
  return tokens.filter((token) => token.text.length > 0)
}

export function joinedTokenText(tokens: RenderToken[]): string {
  return tokens.map((token) => token.text).join('')
}
