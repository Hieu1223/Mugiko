# API Layer — Frontend Integration Guide

This document describes how the frontend talks to the Mugiko backend: the shared
fetch client, authentication/session handling, Server-Sent Events (SSE), error
conventions, and the endpoint catalog. It complements the machine-readable
[`openapi.yaml`](openapi.yaml); where the two disagree, the Go handlers under
`src/backend` are authoritative.

Manga content is served by a separate provider API, not by the Go API. See
[`manga-interface.md`](manga-interface.md).

---

## 1. Topology and base URLs

```
Browser
  │
  ├── /api/v1/*  ──► frontend server or Vite proxy ──► Go API :8080 ──► PostgreSQL / Redis
  │
  └── provider base URL (e.g. http://localhost:8090/api/v1/builtin-provider/*)
                 ──► manga-server (no auth, direct cross-origin request)
```

| Environment | Frontend | API base used by `apiFetch` |
|-------------|----------|-----------------------------|
| Vite dev (`npm run dev`) | http://localhost:5173 | `/api/v1` proxied to `VITE_API_PROXY_TARGET` (default `http://localhost:8080`) |
| Docker (`server.mjs`) | http://localhost:3000 | `/api/v1` proxied to `API_PROXY_TARGET` (default `http://localhost:8080`) |
| Custom deployment | — | Set `VITE_API_BASE_URL` (for example `https://api.example.com/api/v1`) |

Relevant files:

- `src/frontend/packages/common/src/libs/api.ts` — fetch/SSE client.
- `src/frontend/packages/common/src/libs/session.ts` — session bootstrap.
- `src/frontend/packages/common/src/libs/SessionContext.tsx` — session provider.
- `src/frontend/vite.config.ts` — dev proxy.
- `src/frontend/server.mjs` — production static server + API proxy.
- `scripts/deploy/nginx.conf` — production reverse proxy.

---

## 2. Authentication and sessions

The API uses **Bearer tokens with a type prefix**:

| Header | Meaning |
|--------|---------|
| `Authorization: Bearer user-<firebase_id_token>` | Firebase-authenticated user |
| `Authorization: Bearer admin-<admin_token>` | Admin token |
| `Authorization: Bearer anonymous-<token>` | Anonymous session |

### Anonymous bootstrap

The auth middleware in `src/backend/internal/modules/core/user/middleware/authcontext.go`
has an important behavior: **a request without an `Authorization` header creates
a new anonymous user** and returns the token in the **`Authorization` response
header**.

`bootstrapAnonymousSession()` exploits this:

```ts
import { apiRequest } from '@mugiko/common'

// No token is sent. The API creates an anonymous user and returns the token
// in the response Authorization header.
const result = await apiRequest<UserProfile>('/users/me', { auth: false })
const token = result.headers.get('authorization') // "anonymous-..."
```

`SessionProvider` runs this on first load, persists the session under
`localStorage["mugiko.session"]`, and calls `setApiToken(token)` so later
requests include the header automatically.

### Token lifecycle

- `setApiToken(token)` updates the module-level token used by `apiFetch` and
  `streamServerEvents`.
- A `401` on an authenticated request triggers the registered unauthorized
  handler. `SessionProvider` uses it to create a fresh anonymous session.
- `verifyToken(token)` calls `GET /users/me` with an explicit token and does not
  touch the current session.
- The current UI only accepts **anonymous tokens** for manual entry; user/admin
  login is not wired into the frontend yet.

### Auth rules to remember

- Most handlers still expect a user from middleware, but anonymous sessions
  satisfy that requirement. A missing token is not automatically a `401`; it
  becomes a valid anonymous user.
- Admin-only routes use `RequireAdmin` and return `403`.
- Invalid/expired/unknown token prefixes return `401` with `{ "detail": ... }`.

---

## 3. The shared client

### `apiRequest` / `apiFetch`

```ts
import { apiFetch, apiRequest, type RequestOptions } from '@mugiko/common'

const decks = await apiFetch<Deck[]>('/decks')

const result = await apiRequest<Deck>('/decks', {
  method: 'POST',
  body: { name: 'Core 2k' },
})
// result.data, result.status, result.headers
```

`RequestOptions`:

| Option | Default | Purpose |
|--------|---------|---------|
| `method` | `GET` | HTTP method |
| `body` | — | JSON body; `FormData` is passed through untouched |
| `query` | — | Key/value map serialized with `URLSearchParams`; `undefined`, `null`, and `""` are dropped |
| `signal` | — | `AbortSignal` for cancellation |
| `headers` | — | Extra headers |
| `auth` | `true` | `false` skips the `Authorization` header |
| `token` | — | Explicit token for this request |
| `base` | `VITE_API_BASE_URL` or `/api/v1` | Override the API base (used for external providers) |

Behavior:

- Adds `Authorization: Bearer <token>` when a token applies.
- Adds `Content-Type: application/json` when a JSON body is present.
- Returns `undefined` for `204 No Content`.
- Parses `application/json`, otherwise returns text.
- Throws `ApiError` for non-2xx responses.

### Errors

```ts
export class ApiError extends Error {
  status: number
  detail: string
  payload: unknown
}
```

`errorDetail(error)` produces user-facing text and special-cases `401`, `403`,
`404`, network `TypeError`, and unknown errors.

**Error envelope caveat:** the backend has two shapes.

| Modules | Error body |
|---------|------------|
| user, deck, lookup, AI, subtitle, OCR | `{ "detail": "..." }` |
| manga registry, webnovel, manga-server | `{ "error": "...", "message": "..." }` |

`ApiError.detail` is derived from `detail`; for `{ error }` responses it falls
back to `Request failed (<status>)`. When displaying errors from the manga or
webnovel modules, read `error.payload.error` as a fallback.

### URL helper and health

```ts
import { apiUrl, checkHealth } from '@mugiko/common'

apiUrl('/decks', { page: 2 }) // "/api/v1/decks?page=2"
await checkHealth()           // true when /health responds ok
```

`checkHealth()` uses `VITE_HEALTH_URL` when set, otherwise `/health`.

### React hooks

- `useAsync(loader, deps, { enabled })` — abortable fetch with `data`, `loading`,
  `error`, `forbidden`, `unauthorized`, `reload`, `setData`.
- `useDebounced(value, delay)` — useful for search inputs.
- `useDocumentTitle(title)` — page title convention.

Always include every loader input in `deps`, and pass the provided `signal` to
the API function.

---

## 4. Streaming with SSE

### Why not `EventSource`

`EventSource` cannot send an `Authorization` header, which the API requires.
`streamServerEvents` uses `fetch` and parses the event stream manually:

```ts
import { streamServerEvents } from '@mugiko/common'

await streamServerEvents(
  `/llm-jobs/${id}/status`,
  { signal: controller.signal },
  (event) => {
    if (event.event !== 'status') return
    const status = JSON.parse(event.data)
    if (status.status === 'completed') return false // stop reading
  },
)
```

Parsing details:

- Supports `event:` and multi-line `data:` fields.
- Defaults the event name to `message` when no `event:` is present.
- Ignores comments (`: ping` heartbeats).
- Handles LF and CRLF, including CRLF split across chunks.
- Returning `false` from the callback stops reading and cancels the body.

### Stream endpoints

| Endpoint | Event name | Data payload | Terminal |
|----------|------------|--------------|----------|
| `GET /ai/conversations/{conversation_id}/messages/{message_id}/progress` | `message` (default) | Chat progress JSON: `id`, `conversation_id`, `role`, `content`, `status`, `entity_type`, `entity_id` | Stream stays open; the client stops on `completed` / `failed` |
| `GET /llm-jobs/{job_id}/status` | `status` | `{ "job_id": "...", "status": "queued" \| "processing" \| "completed" \| "failed" }` | Server closes after terminal status |
| `GET /subtitles/{subtitle_id}/status` | `status` | `{ "subtitle_id": "...", "status": "..." }` | Server closes after terminal status |
| `GET /ocr/{ocr_id}/status` | `status` | `{ "ocr_id": "...", "status": "..." }` | Server closes after terminal status |

All streams send a DB snapshot first, then live Pub/Sub updates. The LLM,
subtitle, and OCR streams also re-read the DB every 5 seconds and send a
heartbeat comment every 15 seconds.

### Chat flow used by the AI page

1. Create or select a conversation.
2. `POST /ai/conversations/{id}/messages` with `{ role: "user", content }`.
   The response message has `status: "queued"`.
3. Open the progress stream for the returned message id.
4. On progress:
   - `completed` → reload `GET /ai/conversations/{id}` and render the assistant message.
   - `failed` → show `error`.
5. If the stream closes without a terminal event, poll
   `GET /ai/conversations/{id}` (the AI page retries six times, 1.5s apart)
   until the message reaches `completed` or `failed`.

The assistant message is linked through the user message's
`assistant_message_id` when the worker finishes.

---

## 5. Endpoint catalog

All paths below include the `/api/v1` prefix. Unless marked otherwise, requests
use the session token automatically.

### Health

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/health` | Outside `/api/v1`. `{ "status": "ok" }` |

### Users and auth

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/v1/users/register` | Legacy Firebase registration; body `{name, bio?, email?}`; handler expects a raw Firebase token, but the global auth middleware currently rejects unprefixed tokens, so the frontend does not use it |
| `GET` | `/api/v1/users/me` | Profile; no token creates an anonymous session |
| `PATCH` | `/api/v1/users/me/profile` | Body `{name?, bio?, email?}` |
| `GET` | `/api/v1/admin/users` | Admin; paginated user list |
| `GET` | `/api/v1/admin/users/{user_id}` | Admin |
| `PATCH` | `/api/v1/admin/users/{user_id}/role` | Admin; body `{role}` |
| `PATCH` | `/api/v1/admin/users/{user_id}/deactivate` | Admin |

`UserProfile` fields: `user_id`, `name`, `bio`, `email`, `role`
(`anonymous` / `user` / `admin`), `joined_at`.

### Dictionary lookup

| Method | Path | Query |
|--------|------|-------|
| `GET` | `/api/v1/lookup/word` | `word` |
| `GET` | `/api/v1/lookup/prefix` | `prefix`, `limit` (default 100) |
| `GET` | `/api/v1/lookup/kanji` | `kanji` (exactly one character) |

Responses: `DictionaryEntry`, `PrefixSearchResponse`, `KanjiEntry`. See
`packages/common/src/libs/types.ts`.

### Decks and flashcards

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/v1/decks` | `{name}` |
| `GET` | `/api/v1/decks` | `page`, `page_size` |
| `GET` | `/api/v1/decks/{id}` | Deck + words |
| `PATCH` | `/api/v1/decks/{id}` | Rename |
| `DELETE` | `/api/v1/decks/{id}` | Delete |
| `POST` | `/api/v1/decks/{deck_id}/words` | `{word, meaning}` |
| `GET` | `/api/v1/decks/{deck_id}/words` | `page`, `page_size` |
| `PATCH` | `/api/v1/decks/{deck_id}/words/{word_id}` | Update |
| `DELETE` | `/api/v1/decks/{deck_id}/words/{word_id}` | Delete |

### AI chat and LLM jobs

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/v1/ai/conversations` | `{title?}`; defaults to `"New conversation"` |
| `GET` | `/api/v1/ai/conversations` | Array of conversations, newest first |
| `GET` | `/api/v1/ai/conversations/{conversation_id}` | Conversation with `messages[]` |
| `DELETE` | `/api/v1/ai/conversations/{conversation_id}` | `204` |
| `POST` | `/api/v1/ai/conversations/{conversation_id}/messages` | `{role?, content}`; user messages start `queued` |
| `GET` | `/api/v1/ai/conversations/{conversation_id}/messages/{message_id}/progress` | SSE |
| `POST` | `/api/v1/llm-jobs` | `{prompt}`; legacy one-shot job path |
| `GET` | `/api/v1/llm-jobs/{job_id}` | Job including `response` / `error` |
| `GET` | `/api/v1/llm-jobs/{job_id}/status` | SSE |

Actual conversation fields: `id`, `user_id`, `title`, `created_at`,
`updated_at`, and `messages[]` only on the detail endpoint.

Actual message fields: `id`, `conversation_id`, `role`, `content`, `status`,
`error`, `assistant_message_id`, `metadata`, `created_at`, `updated_at`.
Optional fields (`error`, `assistant_message_id`) are omitted while empty, and
`metadata` is currently encoded as `null` because the conversation queries do
not scan it yet.

> The frontend package still exposes a `chatCompletion()` helper targeting
> `/ai/chat/completions`, but that route is not registered by the Go API. Use
> the conversation + message + SSE flow.

### Subtitles

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/v1/subtitle-providers` | Provider list with services |
| `POST` | `/api/v1/subtitle-providers` | Admin only |
| `GET` | `/api/v1/subtitles` | Requires `video_url`; `limit`, `offset` |
| `POST` | `/api/v1/subtitles` | `{video_url, provider_id, service_key}` |
| `GET` | `/api/v1/subtitles/{subtitle_id}` | Subtitle row |
| `GET` | `/api/v1/subtitles/{subtitle_id}/status` | SSE |
| `GET` | `/api/v1/subtitles/{subtitle_id}/segments` | Paginated segments |
| `GET` | `/api/v1/users/me/subtitle-history` | Paginated history |
| `GET` | `/api/v1/users/me/subtitle-settings` | User settings |
| `PUT` | `/api/v1/users/me/subtitle-settings` | `{schema_version, data}` |
| `GET` | `/api/v1/subtitles/{subtitle_id}/state` | Per-subtitle user state |
| `PUT` | `/api/v1/subtitles/{subtitle_id}/state` | `{schema_version, data}` |

Status values: `queued` → `processing` → `completed` | `failed`.

### OCR

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/v1/ocr` | `{image_url}` |
| `GET` | `/api/v1/ocr/{ocr_id}` | Job including `ocr_data` |
| `GET` | `/api/v1/ocr/{ocr_id}/status` | SSE |

### Manga registry

These are **control-plane** endpoints. Content comes from the provider's
`base_url`; see [`manga-interface.md`](manga-interface.md).

| Method | Path | Notes |
|--------|------|-------|
| `GET` | `/api/v1/manga/providers` | Owned + public providers |
| `POST` | `/api/v1/manga/providers` | `{name, base_url, visibility}` |
| `GET` | `/api/v1/manga/providers/{provider_id}` | Owner or admin |
| `PUT` | `/api/v1/manga/providers/{provider_id}` | Owner or admin; built-in rejected |
| `DELETE` | `/api/v1/manga/providers/{provider_id}` | Owner or admin; built-in rejected |
| `POST` | `/api/v1/manga/providers/{provider_id}/subscribe` | `204` |
| `DELETE` | `/api/v1/manga/providers/{provider_id}/subscribe` | `204` |
| `GET` | `/api/v1/manga/subscriptions` | Subscriptions with provider |
| `GET` | `/api/v1/manga/providers/{provider_id}/subscribed` | `{subscribed: boolean}` |
| `POST` | `/api/v1/manga/history` | `{provider_id, manga_id, chapter_id, page_index?, title, cover_url?}` |
| `GET` | `/api/v1/manga/history` | `page`, `page_size`; `{items,total,page,page_size}` |
| `DELETE` | `/api/v1/manga/providers/{provider_id}/history/{manga_id}` | `204` |
| `GET` | `/api/v1/users/me/manga-settings` | `{user_id, schema_version, data, updated_at}` |
| `PUT` | `/api/v1/users/me/manga-settings` | `{schema_version?, data?}` |

### Web novels

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/api/v1/webnovel/novels` | Add a novel by source URL |
| `GET` | `/api/v1/webnovel/novels` | Current user's novels |
| `GET` | `/api/v1/webnovel/novels/all` | All novels |
| `GET` | `/api/v1/webnovel/novels/{novel_id}` | Novel detail |
| `POST` | `/api/v1/webnovel/preview` | Preview before adding |
| `POST` | `/api/v1/webnovel/search` | Search sources |
| `GET` | `/api/v1/webnovel/chapters/{chapter_id}` | Chapter content |

Web novel list/detail responses use `{error}` envelopes on failure.

---

## 6. Pagination and data conventions

Two pagination styles exist:

| Style | Shape | Used by |
|-------|-------|---------|
| Page-based | `{ items, page, page_size, total, total_pages }` | Manga server, some API lists |
| Offset-based | `{ items, total, limit, offset }` | Subtitle segments/history |
| Bespoke | `{ decks, page, page_size, total, total_pages }` | Decks |
| Bare array | `[...]` | Conversations, providers, subscriptions |

Additional conventions:

- IDs are UUID strings unless a module says otherwise (manga content IDs and
  slugs are opaque strings).
- Timestamps are RFC 3339 strings.
- Optional fields are omitted when empty in many Go DTOs; always guard before
  rendering.
- `DELETE` endpoints commonly return `204 No Content`.
- The API is CORS-enabled for direct manga-server content; API requests are
  expected to go through the same-origin proxy.

---

## 7. Adding a new API-backed feature

1. Add a typed function in the relevant frontend package's `libs/` module:
   ```ts
   export async function listThings(signal?: AbortSignal): Promise<Thing[]> {
     return apiFetch<Thing[]>('/things', { signal })
   }
   ```
2. Reuse `useAsync` and pass the signal so navigation cancels in-flight work.
3. Map errors with `errorDetail`; inspect `ApiError.status` for `403` / `404`
   empty states.
4. If the endpoint streams, use `streamServerEvents` and always include a DB
   reconciliation path.
5. Add the endpoint to this catalog and, when it is a stable public contract,
   to `openapi.yaml`.
6. Keep the request path relative (`/things`) so `VITE_API_BASE_URL` and the
   proxies keep working in every environment.

## 8. Related documents

- [`manga-interface.md`](manga-interface.md) — provider/content API and page recipes.
- [`openapi.yaml`](openapi.yaml) — request/response schemas for most API modules.
- [`../README.md`](../README.md) — service topology and run commands.
