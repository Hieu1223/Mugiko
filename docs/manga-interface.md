# Manga Interface — Frontend Guide

This document defines the manga contract used by the frontend. It covers both
layers:

1. **Control plane** — the Go API's manga module (`/api/v1/manga/...`), which
   stores providers, subscriptions, reading history, and settings in
   PostgreSQL.
2. **Content plane** — a standalone manga server reached through a provider's
   `base_url` (by default `http://localhost:8090`), which serves the library,
   chapters, and pages from SQLite.

The browser calls the control plane through the normal authenticated API client
and calls the content plane **directly**, with no session token.

Source files:

| Concern | File |
|---------|------|
| Content API handlers | `src/manga-server/internal/api/api.go` |
| Content API storage/filters | `src/manga-server/internal/store/store.go` |
| Content schema | `src/manga-server/internal/sqlite/sqlite.go` |
| JSON importer | `src/manga-server/internal/importer/importer.go` |
| Built-in provider seed | `src/backend/internal/modules/media/manga/service/seed.go` |
| Control-plane routes | `src/backend/internal/modules/media/manga/api/routes/routes.go` |
| Control-plane DTOs | `src/backend/internal/modules/media/manga/dto/manga.go` |
| Frontend client | `src/frontend/packages/manga/src/libs/manga.ts` |
| Frontend types | `src/frontend/packages/manga/src/libs/types.ts` |

---

## 1. How the two layers connect

```
                 GET /api/v1/manga/providers
Browser ───────────────────────────────────────► Go API :8080
   │                                                │
   │  [{ id, name, base_url, is_builtin, ... }]     │ PostgreSQL
   │◄───────────────────────────────────────────────┘
   │
   │  GET {base_url}/api/v1/builtin-provider/...
   │  (no Authorization header)
   ▼
manga-server :8090 ──► SQLite manga.db
```

The API seeds one **built-in provider** on every startup:

| Field | Value |
|-------|-------|
| `name` | `Mugiko Manga Server` |
| `base_url` | `http://localhost:8090` |
| `visibility` | `public` |
| `is_builtin` | `true` |

Because it is public, it is returned to every authenticated (including
anonymous) user by `GET /api/v1/manga/providers`.

### Frontend provider resolution

`resolveBaseUrl()` in `src/frontend/packages/manga/src/libs/manga.ts`:

1. Calls `/manga/providers` through `apiFetch` (authenticated).
2. Finds the first provider with `is_builtin === true` and a non-empty
   `base_url`.
3. Caches the URL (trailing slashes removed).
4. Sends all content calls to that base with `auth: false`.

```ts
const providers = await apiFetch<MangaProviderDTO[]>('/manga/providers', { auth: true })
const builtin = providers.find((p) => p.is_builtin && p.base_url)
if (!builtin) throw new Error('No built-in manga provider is configured')
const base = builtin.base_url.replace(/\/+$/, '')
```

If the API returns no built-in provider, the frontend shows an error. Make sure
the API started successfully; the seed runs before the HTTP server begins
listening.

> The built-in `base_url` is currently hard-coded in `seed.go`. If the manga
> server is exposed on a different host/port, update that seed value (or add a
> user-owned provider pointing at the real URL).

---

## 2. Content plane contract

Base URL: the selected provider's `base_url`, for example
`http://localhost:8090`.

Characteristics:

- Read-only, `GET` only (plus `GET /health`).
- JSON responses, no envelope, no auth.
- CORS: `Access-Control-Allow-Origin: *`, `GET, OPTIONS`, `Content-Type`.
- All content endpoints are under `/api/v1/builtin-provider`.
- Pagination uses `{ items, page, page_size, total, total_pages }`.
- Not-found errors use `{ "error": "MANGA_NOT_FOUND" | "CHAPTER_NOT_FOUND", "message": "..." }`.

### Endpoint summary

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | `{ "status": "ok" }` |
| `GET` | `/api/v1/builtin-provider/info` | Provider metadata |
| `GET` | `/api/v1/builtin-provider/tags` | Paginated tags |
| `GET` | `/api/v1/builtin-provider/filters` | All tags grouped by category |
| `GET` | `/api/v1/builtin-provider/manga` | Paginated manga search |
| `GET` | `/api/v1/builtin-provider/manga/{id_or_slug}` | Manga detail |
| `GET` | `/api/v1/builtin-provider/manga/{id_or_slug}/chapters` | Chapters of a manga |
| `GET` | `/api/v1/builtin-provider/chapters?manga_id={id_or_slug}` | Chapters (query form) |
| `GET` | `/api/v1/builtin-provider/chapters/{chapter_id}` | Chapter detail with all pages |
| `GET` | `/api/v1/builtin-provider/chapters/{chapter_id}/pages` | Paginated chapter pages |

### 2.1 Provider info

```http
GET /api/v1/builtin-provider/info
```

```json
{
  "name": "Mugiko Manga Server",
  "description": "Standalone manga server backed by SQLite",
  "api_version": "1"
}
```

Use this for a provider header or capability check if you support multiple
providers.

### 2.2 Tags

```http
GET /api/v1/builtin-provider/tags?category=genre&q=action&order=asc&page=1&page_size=50
```

| Query | Default | Notes |
|-------|---------|-------|
| `category` | — | Exact category: `genre`, `series-author`, `artist`, `status`, `type` |
| `q` | — | Case-insensitive substring of name or slug |
| `order` | `asc` | `asc` / `desc`, sorts by name |
| `page` | `1` | |
| `page_size` | `50` | Capped at `200` |

```json
{
  "items": [
    { "id": "…", "name": "Action", "slug": "action", "category": "genre" }
  ],
  "page": 1,
  "page_size": 50,
  "total": 1,
  "total_pages": 1
}
```

### 2.3 Filters

```http
GET /api/v1/builtin-provider/filters
```

Returns **every** tag grouped by category in one call. This is the best endpoint
for building filter selects.

```json
{
  "items": {
    "genre": [
      { "id": "…", "name": "Action", "slug": "action", "category": "genre" }
    ],
    "status": [
      { "id": "…", "name": "Ongoing", "slug": "ongoing", "category": "status" }
    ],
    "type": [
      { "id": "…", "name": "Manga", "slug": "manga", "category": "type" }
    ]
  }
}
```

Categories are data-driven; do not assume every deployment has the same keys.
The current UI reads `genre`, `status`, and `type`, and keeps `series-author`
(`author`) and `artist` as free-text inputs.

### 2.4 Manga list

```http
GET /api/v1/builtin-provider/manga
    ?q=frieren
    &genre=adventure
    &author=yamada
    &artist=…
    &status=ongoing
    &type=manga
    &tags=action,romance
    &year=2020
    &min_score=7.5
    &sort=score
    &order=desc
    &page=1
    &page_size=24
```

| Query | Behavior |
|-------|----------|
| `q` | Lowercased substring match against the imported `search_text` (title, alternative titles, description, summary, tag names/slugs/categories) |
| `tags` | Comma-separated terms; **each term must match at least one tag** (AND across terms, OR between slug/name), substring match |
| `genre` | Tag category `genre`; slug/name substring match |
| `author` | Category `series-author` |
| `artist` | Category `artist` |
| `status` | Category `status` |
| `type` | Category `type` |
| `year` | Exact `release_year` |
| `min_score` | `score >= value` |
| `sort` | `updated_at` (default), `created_at` / `created`, `title`, `score`, `views`, `released` / `release_year` |
| `order` | `asc` (default) or `desc` |
| `page` | Default `1` |
| `page_size` | Default `20`, capped at `100` |

Important: if you want newest-first, pass `sort=updated_at&order=desc`
explicitly. The server default order is ascending.

Response: `MangaListResponse` containing `MangaSummary` items. Each item includes
up to **3 latest chapters** (`latest_chapters`), loaded with
`sort=published_at&order=desc` server-side.

### 2.5 Manga detail

```http
GET /api/v1/builtin-provider/manga/frieren
GET /api/v1/builtin-provider/manga/8f14e45f-ea0c-…
```

The path value is resolved as an **ID first, then as a slug**. This means the
frontend can link by either; the current UI links by `manga.slug`.

Response: `MangaDetail` (all summary fields plus `description`, `source_url`,
`created_at`).

Errors: `404` with `{ "error": "MANGA_NOT_FOUND" }`.

### 2.6 Chapters of a manga

Two equivalent forms:

```http
GET /api/v1/builtin-provider/manga/frieren/chapters?page=1&page_size=50&sort=source_index&order=asc
GET /api/v1/builtin-provider/chapters?manga_id=frieren&page=1&page_size=50&sort=source_index&order=asc
```

| Query | Default | Notes |
|-------|---------|-------|
| `manga_id` | required (query form only) | ID or slug |
| `sort` | `source_index` | Also `published_at`, `number` |
| `order` | `asc` | `asc` / `desc` |
| `page` | `1` | |
| `page_size` | `50` | Capped at `200` |

Response: `ChapterListResponse` of `ChapterSummary`.

### 2.7 Chapter detail

```http
GET /api/v1/builtin-provider/chapters/{chapter_id}
```

`chapter_id` is the chapter UUID from a chapter summary (not the chapter
number). The response embeds **all pages** in order:

```json
{
  "id": "…",
  "manga_id": "…",
  "number": "1",
  "title": "Chapter 1",
  "published_at": "2024-01-01T00:00:00Z",
  "page_count": 18,
  "pages": [
    { "index": 0, "url": "https://cdn.example.com/1.jpg", "width": 0, "height": 0 }
  ]
}
```

The top-level `width`/`height` fields are **not** part of the chapter-detail
response; only the page list endpoint returns them.

### 2.8 Chapter pages

```http
GET /api/v1/builtin-provider/chapters/{chapter_id}/pages?page=1&page_size=50
```

| Query | Default | Notes |
|-------|---------|-------|
| `page` | `1` | |
| `page_size` | `50` | Capped at `200` |

```json
{
  "chapter_id": "…",
  "width": 1200,
  "height": 1800,
  "pages": [
    { "index": 0, "url": "https://cdn.example.com/1.jpg", "width": 1200, "height": 1800 }
  ],
  "page": 1,
  "page_size": 50,
  "total": 18,
  "total_pages": 1
}
```

`width`/`height` at the top level are the maximum dimensions **in the returned
page slice**, not necessarily the whole chapter. `index` is zero-based.

> Imported pages currently store `width = 0` and `height = 0` because the JSON
> importer does not have dimensions. Treat them as optional hints, not layout
> guarantees.

---

## 3. Content data model

### TypeScript contracts

These mirror `src/frontend/packages/manga/src/libs/types.ts`.

```ts
export interface MangaProviderDTO {
  id: string
  owner_id: string
  name: string
  base_url: string
  visibility: string
  is_builtin: boolean
  created_at: string
  updated_at: string
}

export interface MangaTag {
  id: string
  name: string
  slug: string
  category: string
}

export interface ChapterSummary {
  id: string
  manga_id: string
  number: string          // "1", "10.5" — string, not number
  title: string           // may be empty
  published_at: string    // RFC 3339
  page_count: number
}

export interface MangaSummary {
  id: string
  slug: string
  title: string
  alternative_titles: string[]
  cover_url: string
  thumbnail_url: string
  tags: MangaTag[]
  score: number           // may be 0
  views: number           // may be 0
  latest_chapters: ChapterSummary[]
  updated_at: string
}

export interface MangaDetail extends MangaSummary {
  description: string
  source_url: string
  created_at: string
}

export interface PageSummary {
  index: number           // zero-based
  url: string
  width: number           // may be 0
  height: number          // may be 0
}

export interface ChapterDetail extends ChapterSummary {
  pages: PageSummary[]
}

export interface MangaListResponse {
  items: MangaSummary[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface ChapterListResponse {
  items: ChapterSummary[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface TagListResponse {
  items: MangaTag[]
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface FilterListResponse {
  items: Record<string, MangaTag[]>
}
```

### Field semantics

| Field | Notes |
|-------|-------|
| `id` / `slug` | Both are stable. Detail and chapter-list routes accept either. Cards use `slug` for URLs. |
| `alternative_titles` | Always an array (empty, never `null`). |
| `tags` | May be empty; ordered by category then name. |
| `latest_chapters` | Up to 3, newest `published_at` first; `[]` when the manga has no chapters. `withChapters` is always true for API responses. |
| `cover_url` / `thumbnail_url` | Usually identical; may be empty strings. |
| `description` | HTML has already been stripped by the importer; plain text. |
| `source_url` | Original source page; may be empty. |
| `number` | Extracted from `"Chapter N"` when possible, otherwise the source index as a string. |
| `title` | Source chapter title; may be empty. Fall back to `number` in the UI. |
| `published_at` | Formatted `YYYY-MM-DDTHH:MM:SSZ` (UTC). |
| `page_count` | Imported count, updated after pages are written. |
| `index` | Zero-based page index; render in ascending order. |
| `score` / `views` | Imported metadata; often `0` for missing values. |
| `updated_at` / `created_at` | Server timestamps, formatted without fractional seconds. |

### IDs

Content IDs are deterministic UUIDs derived from namespaced MD5 hashes:

- Manga: slug
- Tag: `(category, slug)`
- Chapter: `(manga_id, source_index)`
- Page: `(chapter_id, idx)`

They are opaque to the frontend. Do not parse them. Use `id` for API calls and
`slug` for friendly manga URLs.

---

## 4. Frontend client usage

The package exposes typed helpers in `src/frontend/packages/manga/src/libs/manga.ts`:

```ts
export async function listManga(
  params: ListMangaParams = {},
  signal?: AbortSignal,
): Promise<MangaListResponse>

export async function getManga(idOrSlug: string, signal?: AbortSignal): Promise<MangaDetail>

export async function listMangaChapters(
  mangaId: string,
  params?: { page?: number; page_size?: number; sort?: string; order?: string },
  signal?: AbortSignal,
): Promise<ChapterListResponse>

export async function getChapter(chapterId: string, signal?: AbortSignal): Promise<ChapterDetail>

export async function listTags(
  params?: { category?: string; q?: string; page_size?: number },
  signal?: AbortSignal,
): Promise<TagListResponse>

export async function listFilters(signal?: AbortSignal): Promise<FilterListResponse>
```

`ListMangaParams`:

```ts
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
```

The raw content API also accepts `year` and `min_score`; add them to this
interface if the UI needs them.

`mangaFetch` resolves the provider base first, then calls `apiFetch` with
`{ base, auth: false }`. The provider lookup itself is cached, so navigating
between manga pages does not re-fetch `/manga/providers`.

### Page recipes

#### Library page

```ts
const filters = useAsync((signal) => listFilters(signal), [])
const results = useAsync(
  (signal) =>
    listManga(
      {
        q: debouncedQuery || undefined,
        genre: genre || undefined,
        status: status || undefined,
        type: type || undefined,
        sort,
        order,
        page,
        page_size: 24,
      },
      signal,
    ),
  [debouncedQuery, genre, status, type, sort, order, page],
)
```

- Debounce free-text search (~300 ms).
- Build selects from `filters.data.items`.
- Reset to page 1 whenever a filter changes.
- Render an empty state when `items.length === 0` after loading.

#### Detail page

```ts
const detail = useAsync((signal) => getManga(mangaId, signal), [mangaId])
const chapters = useAsync(
  (signal) =>
    listMangaChapters(
      mangaId,
      { page: chapterPage, page_size: 50, sort: 'source_index', order: 'asc' },
      signal,
    ),
  [mangaId, chapterPage],
)
```

Use `manga.slug` from a card in the detail URL (`/manga/:mangaId`; the route
accepts both slug and id). Chapter rows link to
`/manga/chapters/:chapterId`.

#### Reader page

```ts
const chapter = useAsync((signal) => getChapter(chapterId, signal), [chapterId])
const manga = useAsync(
  (signal) => (chapter.data ? getManga(chapter.data.manga_id, signal) : Promise.resolve(null)),
  [chapter.data?.manga_id],
)
const allChapters = useAsync(
  (signal) =>
    chapter.data
      ? listMangaChapters(
          chapter.data.manga_id,
          { page_size: 200, sort: 'source_index', order: 'asc' },
          signal,
        )
      : Promise.resolve(null),
  [chapter.data?.manga_id],
)
```

- Find the current chapter in `allChapters.data.items` to compute previous/next.
- Render `chapter.data.pages` in order.
- Use `loading` / `error` states from `useAsync`; abort signals are already
  wired by the hook.

---

## 5. Control plane (Go API)

All paths below are under `/api/v1` and use the normal authenticated client
(`apiFetch`). The manga module returns errors as `{ "error": "..." }`.

### Provider DTO

```ts
export interface MangaProviderDTO {
  id: string
  owner_id: string
  name: string
  base_url: string
  visibility: 'public' | 'private'
  is_builtin: boolean
  created_at: string
  updated_at: string
}
```

### Providers

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/manga/providers` | Providers owned by the current user **plus** all public providers |
| `POST` | `/manga/providers` | Body `{ name, base_url, visibility? }`; defaults to `private` |
| `GET` | `/manga/providers/{provider_id}` | Owner or admin only |
| `PUT` | `/manga/providers/{provider_id}` | Body `{ name?, base_url?, visibility? }`; owner/admin; built-in rejected |
| `DELETE` | `/manga/providers/{provider_id}` | Owner/admin; built-in rejected |

Creating a provider does **not** validate that `base_url` implements the content
contract. Do that in the UI (or probe `/info`) before letting users rely on it.

Current behavior worth knowing:

- A duplicate `(owner_id, base_url)` is rejected by the service
  (`PROVIDER_EXISTS`), but the handler currently maps service errors to `500`.
- Attempts to modify/delete the built-in provider are rejected. Non-owners
  receive `403` from the ownership check; an admin who reaches the service
  receives `500` (the service's built-in-provider error is not mapped). Treat
  any failure on a built-in provider edit as "not allowed".

### Subscriptions

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/manga/providers/{provider_id}/subscribe` | `204`; public or owned providers only |
| `DELETE` | `/manga/providers/{provider_id}/subscribe` | `204` |
| `GET` | `/manga/subscriptions` | `MangaSubscriptionDTO[]` with nested `provider` |
| `GET` | `/manga/providers/{provider_id}/subscribed` | `{ "subscribed": true }` |

### Reading history

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/manga/history` | Body below; returns `{ "status": "ok" }` |
| `GET` | `/manga/history?page=1&page_size=20` | `{ items, total, page, page_size }` |
| `DELETE` | `/manga/providers/{provider_id}/history/{manga_id}` | `204` |

```ts
interface UpsertHistoryRequest {
  provider_id: string
  manga_id: string
  chapter_id: string
  page_index?: number
  title: string
  cover_url?: string
}

interface MangaHistoryDTO {
  user_id: string
  provider_id: string
  manga_id: string
  chapter_id: string
  page_index: number
  title: string
  cover_url?: string
  last_read_at: string
  provider?: MangaProviderDTO
}
```

History is keyed by `(user_id, provider_id, manga_id)`; posting again updates
the chapter/page and `last_read_at`. The reader page should upsert on page
change (debounced) if you add history support to the frontend.

### Settings

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/users/me/manga-settings` | Defaults to `{schema_version: 1, data: {}}` when absent |
| `PUT` | `/users/me/manga-settings` | Body `{ schema_version?, data? }` |

```ts
interface MangaUserSettingsDTO {
  user_id: string
  schema_version: number
  data: Record<string, unknown>
  updated_at: string
}
```

> The current service returns `data: null` even when JSON is stored (the
> decode step is still simplified in `service/manga.go`). Treat manga settings
> as reserved until that is implemented; keep reader preferences in the
> subtitle/user settings or local storage if you need them today.

### Control-plane error statuses

| Status | When |
|--------|------|
| `400` | Invalid UUID, missing `manga_id`, malformed body |
| `401` | Missing/invalid auth context (unusual because anonymous sessions are auto-created) |
| `403` | Provider not owned by the user and not admin; private provider not subscribable |
| `404` | Provider not found |
| `500` | Backend error, duplicate provider, built-in edit attempts |

---

## 6. Building a new manga frontend

A minimum viable frontend needs these five calls:

1. `listFilters()` → populate category selects.
2. `listManga(params)` → library grid + pagination.
3. `getManga(idOrSlug)` → detail header, tags, description, latest chapters.
4. `listMangaChapters(idOrSlug, params)` → chapter table.
5. `getChapter(chapterId)` → reader pages.

Optional control-plane features:

- Provider management: list/create/subscribe.
- Continue-reading shelf: `GET /manga/history`.
- Reader resume position: `page_index` in history.
- Settings: read/write `/users/me/manga-settings` once the service returns data.

### Implementing an alternative provider

A provider is just a base URL that implements the content contract in section 2.
To add one:

1. Implement every endpoint in section 2 with the same JSON shapes.
2. Create the provider through `POST /api/v1/manga/providers` or seed it in the
   backend.
3. Make it `public` if users other than the owner should see it.
4. Ensure the browser can reach the URL directly (CORS + no auth required).

If a source cannot match the contract, add an adapter service that exposes the
contract and point the provider at the adapter.

### Caching and refresh behavior

- The provider list call is cached in the manga package after the first success.
  Call `resetBuiltinProviderCacheForTests()` (test-only) if you change the
  provider in the same page session.
- Content responses are not cached by the client; use local state and
  `useAsync` per page.
- The manga server rebuilds its SQLite DB from JSON only when `import` runs.
  Re-importing updates rows by slug/source index and replaces chapter pages.

---

## 7. Smoke tests

Start the manga server, then:

```powershell
# Health
curl.exe http://localhost:8090/health

# First page, highest rated
curl.exe "http://localhost:8090/api/v1/builtin-provider/manga?page=1&page_size=2&sort=score&order=desc"

# Filters
curl.exe http://localhost:8090/api/v1/builtin-provider/filters

# Tags for one category
curl.exe "http://localhost:8090/api/v1/builtin-provider/tags?category=genre&page_size=5"

# Detail by slug (use a slug from the list response)
curl.exe http://localhost:8090/api/v1/builtin-provider/manga/one-piece

# Chapters
curl.exe "http://localhost:8090/api/v1/builtin-provider/manga/one-piece/chapters?page_size=5&order=asc"

# Chapter detail (use an id from the chapter response)
curl.exe http://localhost:8090/api/v1/builtin-provider/chapters/<chapter-id>
```

Import data first if the database is empty:

```powershell
cd src\manga-server
go run . import --db manga.db --manga ..\..\docs\1.json --chapters ..\..\docs\0.json
go run . serve --db manga.db --addr :8090 --serve-only
```

---

## 8. Gotchas checklist

- **Use `order=desc` explicitly.** The content API defaults to ascending order.
- **`page_size` caps vary:** manga `100`, tags/chapters/pages `200`.
- **`page_count` may disagree with the actual page list** if a chapter was
  imported with a template but no pages; prefer `pages.length` in the reader.
- **Page dimensions may be 0.** Design responsive images with `max-width: 100%`
  rather than relying on `width`/`height`.
- **A page list endpoint returns only a slice**, so its top-level `width` /
  `height` are not chapter-wide maxima.
- **Chapter titles can be empty.** Display `title || number`.
- **Manga detail accepts both id and slug.** Use slug for shareable links.
- **Chapter IDs must be UUIDs**; the app route guards them with `RequireUuid`.
- **Content calls must not send `Authorization`.** They are cross-origin and the
  manga server does not expect credentials.
- **Provider base URLs may include a path.** The client only strips trailing
  slashes and then appends `/api/v1/builtin-provider/...`; providers must expose
  that path at their root.
- **CORS is GET-only.** Do not add custom headers to content requests, or the
  browser will issue a preflight that the manga server does not handle.

## 9. Related documents

- [`api-layer.md`](api-layer.md) — shared API client, auth, SSE, errors.
- [`openapi.yaml`](openapi.yaml) — control-plane request/response schemas.
- [`../src/manga-server/README.md`](../src/manga-server/README.md) — import and serve commands.
- [`../README.md`](../README.md) — full stack topology.
