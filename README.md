# Mugiko

Unified repository for Mugiko projects.

## Architecture

- **API** — Go backend with conversation CRUD, add-message, and chat/SSE progress endpoints.
- **Cache updater** — Go service consuming Sequin progress streams; writes Redis keys with 24h TTL and publishes via Pub/Sub.
- **LLM Work Server** — Go service consuming chat/LLM job streams; atomically claims DB rows, calls NVIDIA NIM, persists assistant/status rows.
- **Subtitle worker** — Python service consuming subtitle job streams; progress is derived from DB writes via Sequin CDC (no direct publishing).
- **Frontend** — React/Vite app; chat uses add-message → SSE → DB reconciliation on stream failure.

## Structure

```
Mugiko/
├── doc/                   # Documentation
├── src/                   # All source code
│   ├── backend/           # Go API server (conversation CRUD, add-message, SSE)
│   ├── cache-updater/     # Go Redis cache updater (24h TTL + Pub/Sub)
│   ├── frontend/          # MugikoFrontend (React/Vite)
│   ├── llm-worker/        # Go LLM Work Server (NIM chat completion)
│   ├── llm/               # llm_server (Python LLM service - superseded by llm-worker)
│   ├── workers/           # MugikoWorkServer (Python subtitle worker only)
│   ├── data/              # MugikoDictionary (dictionary binaries + build scripts)
│   └── web/               # Web subprojects
│       └── anki-decks/    # AnkiDecks (deck generation)
├── scripts/               # Build/deploy scripts
│   ├── backend/
│   ├── frontend/
│   ├── deploy/            # MugikoDeploy (Docker Compose, envs, SQL, Sequin config)
│   ├── workers/
│   ├── data/
│   └── web/
├── docker-compose.yml     # Root compose file (local dev)
├── scripts/deploy/docker-compose.yml  # Production-like compose file
└── .gitignore
```

## Key Design Decisions

### Progress & SSE
- Progress keys: `chat:progress:<id>`, `llm:progress:<id>`, `subtitle:progress:<id>`
- Each progress key stores the latest snapshot as JSON with a 24h TTL (`PROGRESS_TTL_SECONDS=86400`)
- Every progress transition updates the Redis key **and** publishes via Pub/Sub on the same key
- SSE handlers subscribe to Pub/Sub first, read the snapshot key, then fall back to DB state
- Chat progress persistence: `messages` table has `status`, `error`, `assistant_message_id`, `updated_at` columns for DB fallback

### Workers
- **LLM worker** (Go): consumes `chat_jobs` and `llm_jobs` streams; atomic claim via `UPDATE ... WHERE status='queued'`; stale-processing recovery via `XAUTOCLAIM`
- **Subtitle worker** (Python): subtitle-only; no direct progress publishing — progress flows DB → Sequin CDC → progress stream → cache updater
- **Cache updater** (Go): consumes `chat_progress`, `llm_progress`, `subtitle_progress` streams; SET EX + PUBLISH per event; ACK after success

### Sequin (CDC)
- Table-name sources (not stale OIDs)
- `conversation_changes` sink disabled
- Sinks: `subtitle_queue`, `chat_jobs`, `llm_jobs`, `chat_progress`, `llm_progress`, `subtitle_progress`

## Run

```powershell
# Local dev (builds from source)
docker compose down -v
docker compose up

# Production-like
cd scripts/deploy
docker compose down -v
docker compose up
```

## Services (local `docker-compose.yml`)

| Service | Build Context | Purpose |
|---------|--------------|---------|
| postgres | — | PostgreSQL 15, logical replication |
| sequin_redis | — | Redis 7 (AOF) |
| sequin | sequin/sequin | CDC from Postgres → Redis |
| init-db | postgres | One-shot schema + publication/slot setup |
| api | ./src/backend | Go API (conversation CRUD, add-message, SSE) |
| cache-updater | ./src/cache-updater | Go Redis cache updater (24h TTL + Pub/Sub) |
| llm-worker | ./src/llm-worker | Go LLM Work Server (NIM) |
| subtitle-worker | ./src/workers | Python subtitle worker |
| frontend | ./src/frontend | React/Vite app |

## Build

All Go modules build independently:

```powershell
cd src\backend      && go build ./...
cd src\cache-updater && go build ./...
cd src\llm-worker   && go build ./...
```
