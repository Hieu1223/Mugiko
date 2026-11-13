export { Button } from './components/ui/Button'
export { FieldShell, Input, Select, Textarea } from './components/ui/Field'
export { LoadingState, EmptyState, ErrorState, InlineNotice } from './components/ui/States'
export { Dialog } from './components/ui/Dialog'
export { Pagination } from './components/ui/Pagination'
export { PageTitle, Tabs } from './components/ui/Layout'

export { Shell } from './components/Shell'
export { LookupProvider, WordToken, useLookup } from './components/LookupProvider'
export type { WordTokenMode } from './components/LookupProvider'
export { SessionBadge } from './components/SessionBadge'
export { SessionDialog } from './components/SessionDialog'

export { SessionProvider, useSession } from './libs/SessionContext'
export { ToastProvider, useToast } from './libs/ToastContext'
export {
  Link,
  isUuid,
  useNavigate,
  useParams,
  useSearchParams,
} from './libs/router'

export { ApiError, apiFetch, apiRequest, checkHealth, errorDetail, isApiError, streamServerEvents } from './libs/api'
export type { RequestOptions, ServerEvent, StreamOptions } from './libs/api'
export {
  bootstrapAnonymousSession,
  isForbidden,
  isUnauthorized,
  maskToken,
  normalizeAnonymousToken,
  TokenFormatError,
  verifyToken,
} from './libs/session'
export { lookupKanji, lookupPrefix, lookupWord, prefixWithFallback } from './libs/lookup'
export {
  addDeckWord,
  createDeck,
  deleteDeck,
  deleteDeckWord,
  getDeck,
  listAllDecks,
  listDeckWords,
  listDecks,
  renameDeck,
  updateDeckWord,
} from './libs/decks'
export { useAsync, useDebounced, useDocumentTitle } from './libs/hooks'

export { normalizeTokens, joinedTokenText } from './utils/tokens'
export type { RenderToken } from './utils/tokens'
export {
  cx,
  formatDate,
  formatMs,
  padNumber,
  relativeDate,
  shortId,
  truncate,
} from './utils/format'
export type {
  Deck,
  DeckWord,
  DictionaryEntry,
  DictionaryReading,
  KanjiEntry,
  PaginatedDecks,
  PaginatedDeckWords,
  PrefixSearchResponse,
  UserProfile,
} from './libs/types'

export { LookupPage } from './pages/LookupPage'
export { DecksPage } from './pages/DecksPage'
export { DeckDetailPage } from './pages/DeckDetailPage'

export type { NavItem, SiteNav } from './components/Shell'
