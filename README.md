# Mugiko

Mugiko is a self-hosted Japanese-learning platform. A single React application
combines subtitle study, web novels, manga reading, dictionary lookup,
flashcards, OCR, and an AI chat workspace. A Go API owns authentication and
user data; background workers process LLM, subtitle, and OCR jobs; a standalone
Go manga server serves the manga library.

## Services

| Service | Language | Port | Responsibility |
|---------|----------|------|----------------|
| `frontend` | React 19 + Vite 6 | 3000 (prod), 5173 (dev) | Web UI for all study tools |
| `api` | Go 1.27 | 8080 | Auth, profiles, conversations/chat, decks, lookup, subtitle/OCR/LLM job APIs, manga provider registry |
| `manga-server` | Go 1.27 + SQLite | 8090 | Read-only manga content API (library, tags, chapters, pages) |
| `llm-worker` | Go 1.27 | — | Consumes chat/LLM jobs, calls NVIDIA NIM, writes assistant messages |
| `subtitle-worker` | Python 3.12 | — | Downloads and tokenizes YouTube subtitles into DB segments |
| `ocr-worker` | Go 1.27 | — | Consumes OCR jobs and calls the NVIDIA NIM parse endpoint |
| `cache-updater` | Go 1.27 | — | Consumes progress streams, writes 24h Redis snapshots, publishes Pub/Sub |
| `postgres` | PostgreSQL 15 | 5432 | Primary data store, logical replication enabled |
| `sequin_redis` | Redis 7 | 6379 | Streams, progress snapshots, Pub/Sub |
| `sequin` | Sequin | 7376 | CDC from PostgreSQL to Redis streams |

## Architecture

```
                    ┌─────────────────────────────┐
                    │        Browser (React)       │
                    └──────────────┬──────────────┘
                                   │
                 app data /auth    │    manga content (direct, no auth)
                                   ▼
                    ┌─────────────────────────────┐        ┌──────────────────────┐
                    │        Go API (:8080)        │        │ manga-server (:8090) │
                    └───────┬──────────────┬───────┘        │  SQLite + JSON import │
                            │              │                └──────────────────────┘
                            ▼              ▼
                    ┌────────────┐  ┌────────────┐
                    │ PostgreSQL │  │   Redis    │◄──────────────┐
                    └─────┬──────┘  └─────┬──────┘               │
                          │               │                      │
                          │ Sequin CDC    │ streams / Pub/Sub    │
                          ▼               ▼                      │
                    ┌─────────────────────────────┐              │
                    │ cache-updater                │              │
                    │ llm-worker                   │──────────────┘
                    │ subtitle-worker              │
                    │ ocr-worker                   │
                    └─────────────────────────────┘
```

The frontend talks to the API for application data. Manga content is different:
the API only stores a **provider registry** (name + `base_url`), and the browser
calls the built-in manga server directly at that base URL. See
[`docs/manga-interface.md`](docs/manga-interface.md).

## Repository layout

```
Mugiko/
├── docs/
│   ├── api-layer.md            # Frontend API client + backend endpoint reference
│   ├── manga-interface.md      # Manga provider/content contract for frontend work
│   ├── openapi.yaml            # OpenAPI 3 spec for the Go API
│   └── inventory.md            # Project/service inventory
├── scripts/
│   └── deploy/                 # Production-like Docker Compose stack
│       ├── docker-compose.yml
│       ├── playground.yml      # Sequin CDC sources, transforms, sinks
│       ├── nginx.conf
│       ├── envs/
│       └── sql/
│           ├── setup/          # PostgreSQL schema and seeds
│           └── sequin/         # Sequin enrichment SQL
└── src/
    ├── backend/                # Go API (modules: user, ai, deck, lookup, manga, subtitle, OCR, webnovel)
    ├── cache-updater/          # Go progress cache updater
    ├── frontend/               # React/Vite monorepo (packages: common, ai, manga, subtitle, webnovel)
    ├── llm-worker/             # Go LLM/chat worker
    ├── manga-server/           # Standalone Go + SQLite manga content server
    ├── ocr-worker/             # Go OCR worker
    └── workers/                # Python subtitle worker
```

## Quick start

### Full stack (Docker Compose)

Requirements: Docker Desktop with Compose v2.

```powershell
cd scripts\deploy

# The Sequin secrets are read from scripts/deploy/.env.
# They can be regenerated with:
#   openssl rand -base64 48   -> SEQUIN_SECRET_KEY_BASE
#   openssl rand -base64 32   -> SEQUIN_VAULT_KEY

docker compose up --build
```

Runtime files mounted into containers:

| File | Used by | Purpose |
|------|---------|---------|
| `src/workers/nim.txt` | `llm-worker`, `subtitle-worker`, `ocr-worker` | NVIDIA NIM API keys |
| `scripts/deploy/groq.txt` | `subtitle-worker` | Groq keys for subtitle translation/processing |
| `scripts/deploy/cookies.txt` | `subtitle-worker` | Optional YouTube cookies for yt-dlp |
| `docs/1.json`, `docs/0.json` | `manga-server` | Manga and chapter seed data |

Once healthy:

| URL | Service |
|-----|---------|
| http://localhost:3000 | Frontend |
| http://localhost:8080/health | API health |
| http://localhost:8090/health | Manga server health |
| http://localhost:7376 | Sequin UI |

### Frontend only

```powershell
cd src\frontend
npm install
npm run dev
```

Vite proxies `/api` and `/health` to `VITE_API_PROXY_TARGET` (default
`http://localhost:8080`). Use `VITE_API_BASE_URL` to point the browser at an
absolute API URL instead.

### Manga server only

```powershell
cd src\manga-server
go run . import --db manga.db --manga ..\..\docs\1.json --chapters ..\..\docs\0.json
go run . serve --db manga.db --addr :8090 --serve-only
```

### API only

```powershell
cd src\backend
$env:DB_DRIVER="postgres"
$env:DB_PATH="postgres://postgres:postgres@localhost:5432/mugiko?sslmode=disable"
$env:REDIS_URL="redis://localhost:6379/0"
go run ./cmd/server
```

## Core flows

### Chat (AI)

1. `POST /api/v1/ai/conversations` creates a conversation.
2. `POST /api/v1/ai/conversations/{id}/messages` inserts a user message with
   `status=queued`.
3. Sequin detects the insert, writes it to the `chat_jobs` Redis stream, and the
   Go `llm-worker` claims it.
4. The worker calls NVIDIA NIM, inserts the assistant message, and updates the
   user message status (`processing` → `completed` / `failed`).
5. Every status write is captured by Sequin (`chat_progress` stream), stored by
   `cache-updater` as `chat:progress:<message_id>` (24h TTL), and published on
   the same key. The API's SSE endpoint forwards those payloads.
6. If the stream closes early, the frontend reconciles from
   `GET /api/v1/ai/conversations/{id}` until a terminal status is reached.

### Subtitles

`POST /api/v1/subtitles` creates a queued row. Sequin forwards it to
`subtitle_queue`; the Python worker crawls YouTube (json3), tokenizes with
Janome, and writes segments. Progress follows the same DB → Sequin →
`subtitle_progress` → `cache-updater` → SSE path.

### Manga

The API seeds a public built-in provider (`Mugiko Manga Server`,
`http://localhost:8090`) at startup. The frontend lists providers through
`GET /api/v1/manga/providers`, picks the built-in one, then calls its
`/api/v1/builtin-provider/...` content endpoints directly with no session
token. Details, schemas, and page recipes are in
[`docs/manga-interface.md`](docs/manga-interface.md).

### OCR

`POST /api/v1/ocr` queues an image URL. Sequin routes inserts to `ocr_jobs`;
the Go OCR worker calls the NVIDIA NIM parse endpoint and persists
`ocr_results`. Status updates stream through `ocr:progress:<id>`.

## Progress and reliability

- Progress keys: `chat:progress:<id>`, `llm:progress:<id>`,
  `subtitle:progress:<id>`, `ocr:progress:<id>`.
- Snapshots are JSON with a 24h TTL (`PROGRESS_TTL_SECONDS=86400`).
- Each transition writes the key **and** publishes via Pub/Sub on the same key.
- SSE handlers subscribe first, send a DB snapshot, then forward live updates;
  `llm`, `subtitle`, and `ocr` streams also reconcile from the DB every 5s.
- Workers use Redis consumer groups and acknowledge only after successful
  processing. Stale pending messages are reclaimed (`XAUTOCLAIM`), and DB rows
  are claimed atomically where applicable.
- `llm-worker`, `subtitle-worker`, and `ocr-worker` are at-least-once; handlers
  and DB writes are idempotent.

## Documentation

| Document | Contents |
|----------|----------|
| [`docs/api-layer.md`](docs/api-layer.md) | Frontend API client (`apiFetch`, auth, SSE, errors), endpoint catalog, chat integration patterns |
| [`docs/manga-interface.md`](docs/manga-interface.md) | Manga provider registry, full content API, TypeScript contracts, page-building guide |
| [`docs/openapi.yaml`](docs/openapi.yaml) | OpenAPI 3 spec for the Go API |
| [`docs/inventory.md`](docs/inventory.md) | Detailed per-project inventory and environment variables |
| [`src/manga-server/README.md`](src/manga-server/README.md) | Manga server import/serve commands |
| [`src/workers/README.md`](src/workers/README.md) | Subtitle worker pipeline, cache, and status flow |

## Build and test

Each Go module builds independently:

```powershell
cd src\backend       ; go build ./... ; go test ./... ; go vet ./...
cd src\cache-updater ; go build ./...
cd src\llm-worker    ; go build ./...
cd src\manga-server  ; go build ./... ; go test ./... ; go vet ./...
cd src\ocr-worker    ; go build ./...
```

Frontend:

```powershell
cd src\frontend
npm run typecheck
npm run build
```

Subtitle worker:

```powershell
cd src\workers
pip install -r requirements.txt
copy .env.example .env
python -m src.main
```

## Design notes

- **Single frontend, multiple feature packages.** `src/frontend/packages/*`
  are npm workspaces exposed through Vite aliases; feature pages are lazily
  loaded from `src/frontend/src/App.tsx`.
- **API owns identity, providers own content.** The backend never proxies manga
  images or chapter data. Provider URLs are data, so new manga sources can be
  added without changing the API.
- **Redis is a projection, PostgreSQL is the source of truth.** Progress and
  job streams are rebuildable; clients always have a DB reconciliation path.
- **Sequin is the only CDC bridge.** Services do not publish progress directly;
  they write the DB and let CDC + `cache-updater` fan out.
- **The API auto-creates anonymous users.** Requests without an `Authorization`
  header receive a fresh anonymous token in the response header; the frontend
  bootstraps and persists it.
