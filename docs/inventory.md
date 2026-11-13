# Mugiko Projects Inventory

> Generated on: 2026-11-05
> Scanned locations: `/c/Projects/Mugiko`

---

## 1. Mugiko Backend (Go API)

**Root Directory:** `src/backend/`

### Key Subdirectories
| Path | Purpose |
|------|---------|
| `cmd/server/` | Main application entry point |
| `internal/common/` | Shared utilities, config, database, Redis client |
| `internal/modules/` | Business logic modules (AI, user, manga, OCR, etc.) |
| `asset/` | Static assets (loaded at runtime) |

### Build System
- **Language:** Go 1.27.2
- **Build Tool:** `go build` via Docker multi-stage
- **Dockerfile:** Multi-stage (golang:1.27-alpine → alpine:3.18)

### Exposed Ports
- **8080** (HTTP server, configurable via `PORT` env)

### Environment Variables
| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `PORT` | `8080` | No | HTTP listen port |
| `LOG_DIR` | `/app/logs` | No | Writable directory for error.log |
| `DB_DRIVER` | `postgres` | No | database/sql driver |
| `DB_PATH` | — | **Yes** | Driver-specific DSN (e.g., `postgres://user:pass@host:5432/db?sslmode=disable`) |
| `REDIS_URL` | `redis://localhost:6379/0` | **Yes** | Redis connection for Pub/Sub |

### Routes
- `POST /api/v1/ai/conversations` — create conversation
- `GET /api/v1/ai/conversations` — list conversations by user
- `GET /api/v1/ai/conversations/{conversation_id}` — get conversation + messages
- `DELETE /api/v1/ai/conversations/{conversation_id}` — delete conversation
- `POST /api/v1/ai/conversations/{conversation_id}/messages` — add message (queued for assistant)
- `GET /api/v1/ai/conversations/{conversation_id}/messages/{message_id}/progress` — SSE progress (Pub/Sub + DB fallback)
- `POST /api/v1/llm-jobs` — create LLM job
- `GET /api/v1/llm-jobs/{job_id}` — get LLM job
- `GET /api/v1/llm-jobs/{job_id}/status` — SSE job status (Pub/Sub + DB fallback)

---

## 2. Cache Updater (Go)

**Root Directory:** `src/cache-updater/`

Consumes Sequin progress streams (`chat_progress`, `llm_progress`, `subtitle_progress`), writes each event as a Redis key with 24h TTL (`SET EX`), and publishes via Pub/Sub on the same key. ACKs after `SET EX` + `PUBLISH` succeed.

### Key Subdirectories
| Path | Purpose |
|------|---------|
| `main.go` | Entry point |
| `internal/updater/updater.go` | Consumer group + XReadGroup loop |

### Build System
- **Language:** Go 1.27.2
- **Dockerfile:** Multi-stage (golang:1.27-alpine → alpine:3.18)

### Environment Variables
| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | **Yes** | Redis connection |
| `PROGRESS_STREAMS` | `chat_progress,llm_progress,subtitle_progress` | No | Comma-separated progress stream names |
| `CONSUMER_GROUP` | `cache-updater` | No | Redis consumer group |
| `CONSUMER_NAME` | `cache-updater-1` | No | Consumer name |
| `PROGRESS_TTL_SECONDS` | `86400` | No | Progress key TTL (24 hours) |

### Progress Keys
| Key Format | Purpose |
|------------|---------|
| `chat:progress:<id>` | Chat message progress snapshot |
| `llm:progress:<id>` | LLM job progress snapshot |
| `subtitle:progress:<id>` | Subtitle job progress snapshot |

---

## 3. LLM Work Server (Go)

**Root Directory:** `src/llm-worker/`

Consumes `chat_jobs` and `llm_jobs` Redis streams, atomically claims DB rows via `UPDATE ... WHERE status='queued'`, calls NVIDIA NIM chat completions, persists assistant messages / job responses, and handles stale-processing recovery via `XAUTOCLAIM`. Publishes progress events to `chat_progress` / `llm_progress` streams.

### Key Subdirectories
| Path | Purpose |
|------|---------|
| `main.go` | Entry point |
| `internal/worker/worker.go` | Consumer loop, DB claims, NIM calls, persistence |
| `internal/worker/nim_client.go` | NVIDIA NIM OpenAI-compatible client |

### Build System
- **Language:** Go 1.27.2
- **Dockerfile:** Multi-stage (golang:1.27-alpine → alpine:3.18)

### Environment Variables
| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `DATABASE_URL` | — | **Yes** | PostgreSQL DSN |
| `REDIS_URL` | `redis://localhost:6379/0` | **Yes** | Redis connection |
| `CONSUMER_GROUP` | `llm-workers` | No | Redis consumer group |
| `CONSUMER_NAME` | `llm-worker-1` | No | Consumer name |
| `LLM_CHAT_JOBS_STREAM` | `chat_jobs` | No | Chat job stream key |
| `LLM_JOBS_STREAM` | `llm_jobs` | No | LLM job stream key |
| `PROGRESS_TTL_SECONDS` | `86400` | No | Progress key TTL |
| `NVIDIA_API_KEYS_FILE` | `nim.txt` | **Yes** | Path to NIM API keys file |
| `NVIDIA_NIM_BASE_URL` | `https://integrate.api.nvidia.com/v1` | No | NIM API base URL |
| `NVIDIA_NIM_MODEL` | `nvidia/nemotron-3-ultra-550b-a55b` | No | Model identifier |
| `NVIDIA_NIM_TEMPERATURE` | `0.2` | No | Sampling temperature |
| `NVIDIA_NIM_MAX_TOKENS` | `4096` | No | Max tokens |
| `NVIDIA_NIM_TIMEOUT_SECONDS` | `120` | No | Request timeout |
| `LLM_READ_BLOCK_MS` | `5000` | No | Redis XREAD block timeout (ms) |
| `LLM_CLAIM_IDLE_MS` | `300000` | No | Stale processing claim timeout (ms) |
| `LLM_POLL_INTERVAL_MS` | `2000` | No | Poll interval (ms) |

---

## 4. Mugiko Frontend

**Root Directory:** `src/frontend/`

### Key Subdirectories
| Path | Purpose |
|------|---------|
| `src/` | Main React application source |
| `packages/` | Monorepo workspaces (`common`, `subtitle`, `webnovel`, `ai`) |
| `dist/` | Build output (gitignored) |
| `node_modules/` | Dependencies (gitignored) |

### Build System
- **Package Manager:** npm (with workspaces)
- **Build Tool:** Vite 6.3.0 + TypeScript 5.8.0
- **Dockerfile:** Multi-stage (node:20-alpine build → node:20-alpine runtime)
- **Scripts:** `dev`, `build`, `typecheck`, `preview`, `start`

### Exposed Ports
- **3000** (HTTP via `server.mjs`, configurable via `PORT` env)

### Environment Variables
| Variable | Example | Required | Description |
|----------|---------|----------|-------------|
| `VITE_API_BASE_URL` | `/api/v1` | No | Base API path (relative) |
| `API_PROXY_TARGET` | `http://api:8080` | No | API proxy target for server.mjs / vite dev |

### Chat Flow
Frontend uses **add-message → SSE → DB reconciliation**:
1. `POST /ai/conversations/{id}/messages` with `{role: 'user', content}` → returns queued user message
2. `GET /ai/conversations/{id}/messages/{msg_id}/progress` → SSE stream of progress events
3. On stream close/failure → poll `GET /ai/conversations/{id}` until terminal status

---

## 5. Subtitle Worker (Python)

**Root Directory:** `src/workers/`

Subtitle-only worker. The LLM worker has been moved to `src/llm-worker/` (Go). Progress is no longer published directly — it flows from DB writes via Sequin CDC → `subtitle_progress` stream → cache updater.

### Key Subdirectories
| Path | Purpose |
|------|---------|
| `src/main.py` | Entrypoint (subtitle only) |
| `src/subtitle/` | Subtitle processing pipeline |
| `src/config.py` | Env config |

### Build System
- **Language:** Python 3.12
- **Package Manager:** pip
- **Dockerfile:** Single-stage (python:3.12-slim)

### Exposed Ports
- **None** (worker process, communicates via Redis streams + PostgreSQL)

### Environment Variables
| Variable | Example | Required | Description |
|----------|---------|----------|-------------|
| `DATABASE_URL` | `postgresql://postgres:***@postgres:5432/mugiko` | **Yes** | PostgreSQL DSN |
| `REDIS_URL` | `redis://sequin_redis:6379/0` | **Yes** | Redis connection |
| `SUBTITLE_STREAM` | `subtitle_queue` | No | Redis stream for subtitle jobs |
| `CONSUMER_GROUP` | `subtitle-workers` | No | Redis consumer group |
| `CONSUMER_NAME` | `subtitle-worker-1` | No | Consumer name |
| `READ_BLOCK_MS` | `2000` | No | XREAD block timeout |
| `CLAIM_IDLE_MS` | `300000` | No | Claim idle timeout |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | `10` | No | Redis socket timeout; defaults to max(10, READ_BLOCK_MS/1000 + 5) |
| `RECOVERY_STALE_SECONDS` | `300` | No | Retry queued/processing jobs stuck longer than this (seconds) |
| `RECOVERY_BATCH_SIZE` | `10` | No | Max stale jobs to recover per batch |
| `SUBTITLE_CACHE_TTL_SECONDS` | `604800` | No | Cache TTL (7 days) |

---

## 6. Mugiko Deploy (Infrastructure)

**Root Directory:** `scripts/deploy/`

### Key Subdirectories
| Path | Purpose |
|------|---------|
| `docker-compose.yml` | Production-like compose |
| `playground.yml` | Sequin CDC configuration |
| `nginx.conf` | Nginx reverse proxy |
| `sql/setup/schema.sql` | Database schema |
| `sql/sequin/` | Sequin CDC SQL |

### Build System
- **Primary:** Docker Compose orchestration
- **No application code** — infrastructure only

### Services Defined (in `docker-compose.yml`)
| Service | Build Context | Purpose |
|---------|--------------|---------|
| `postgres` | — | PostgreSQL 15, logical replication |
| `sequin_redis` | — | Redis 7 (AOF) |
| `sequin` | sequin/sequin | CDC from Postgres → Redis |
| `init-db` | postgres | One-shot schema + publication/slot |
| `api` | `../../src/backend` | Go API |
| `cache-updater` | `../../src/cache-updater` | Go Redis cache updater |
| `llm-worker` | `../../src/llm-worker` | Go LLM Work Server |
| `subtitle-worker` | `../../src/workers` | Python subtitle worker |
| `frontend` | `../../src/frontend` | React frontend |

### Sequin Sinks (in `playground.yml`)
| Sink | Stream | Source Table | Actions |
|------|--------|-------------|---------|
| `mugiko-subtitle-sink` | `subtitle_queue` | `public.subtitles` | insert |
| `mugiko-chat-jobs-sink` | `chat_jobs` | `public.messages` | insert, update |
| `mugiko-llm-jobs-sink` | `llm_jobs` | `public.llm_jobs` | insert, update |
| `mugiko-chat-progress-sink` | `chat_progress` | `public.messages` | update |
| `mugiko-llm-progress-sink` | `llm_progress` | `public.llm_jobs` | update |
| `mugiko-subtitle-progress-sink` | `subtitle_progress` | `public.subtitles` | update |

> The `conversation_changes` sink has been removed.

### Database Schema Changes
The `messages` table now includes chat-progress columns:
- `status TEXT NOT NULL DEFAULT 'completed'`
- `error TEXT`
- `assistant_message_id UUID REFERENCES messages(id) ON DELETE SET NULL`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- Indexes: `idx_messages_status`, `idx_messages_assistant_message_id`

---

## 7. Mugiko Web Server (Unified Monorepo)

**Root Directory:** `/c/Projects/Mugiko/`

This is the unified monorepo containing all sub-projects.

### Docker Compose Services (from `docker-compose.yml`)
| Service | Build Context | Purpose |
|---------|--------------|---------|
| `postgres` | — | Database |
| `sequin_redis` | — | Redis |
| `sequin` | — | CDC |
| `init-db` | postgres | One-shot schema setup |
| `api` | `./src/backend` | Go API |
| `cache-updater` | `./src/cache-updater` | Go Redis cache updater |
| `llm-worker` | `./src/llm-worker` | Go LLM Work Server |
| `subtitle-worker` | `./src/workers` | Python subtitle worker |
| `frontend` | `./src/frontend` | React app |

---

## Project Relationships

```
Mugiko/src/backend/           → Go API server (conversation CRUD, add-message, SSE)
Mugiko/src/cache-updater/     → Go Redis cache updater (24h TTL + Pub/Sub)
Mugiko/src/llm-worker/        → Go LLM Work Server (NIM chat completion)
Mugiko/src/workers/           → Python subtitle worker (subtitle-only)
Mugiko/src/frontend/          → React/Vite frontend
Mugiko/scripts/deploy/        → Deployment scripts (compose, Sequin config, SQL)
```

## Deployment Variants

| Compose File | Use Case | Key Difference |
|--------------|----------|----------------|
| `Mugiko/docker-compose.yml` | Local dev | Builds from source, includes init-db one-shot |
| `Mugiko/scripts/deploy/docker-compose.yml` | Production-like | Same services, absolute paths |

## Shared Infrastructure

- **PostgreSQL:** Port 5432, DB `mugiko`, logical replication enabled for Sequin
- **Redis:** Port 6379, AOF enabled, used by Sequin + all workers + cache updater Pub/Sub
- **Sequin:** Port 7376, CDC from Postgres → Redis streams, config via `playground.yml`

## Critical Runtime Files (Not in Images)

| File | Source | Mounted Into |
|------|--------|--------------|
| `nim.txt` | `src/workers/nim.txt` | `llm-worker`, `subtitle-worker` containers |
| SQL migrations | `scripts/deploy/sql/setup/schema.sql` | `init-db` container, postgres entrypoint |
| Sequin config | `scripts/deploy/playground.yml` | `sequin` container |
