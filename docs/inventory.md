# Mugiko Projects Inventory

> Generated on: 2026-11-03
> Scanned locations: `/c/Projects/`

---

## 1. MugikoGO (Go Backend)

**Root Directory:** `/c/Projects/MugikoGO/`

### Key Subdirectories
| Path | Purpose |
|------|---------|
| `cmd/server/` | Main application entry point |
| `internal/common/` | Shared utilities, config, database |
| `internal/modules/` | Business logic modules |
| `internal/util/` | Helper functions |
| `asset/` | Static assets (loaded at runtime) |
| `scripts/` | Python scripts for DB setup/migration |
| `build/` | Build output (gitignored) |
| `doc/` | Documentation |
| `.cache/` | Go build caches |
| `.github/` | GitHub workflows |

### Build System
- **Primary:** Go modules (`go.mod`, `go.sum`)
- **Build Tool:** `go build` via `Makefile`
- **Dockerfile:** Multi-stage (golang:1.27.2-alpine → alpine:3.22)
- **Makefile Targets:** `build`, `run`, `run-dev`, `setup`, `migrate`, `migrate-docker`, `clean`

### Runtime Dependencies
| Dependency | Version |
|------------|---------|
| `github.com/google/uuid` | v1.6.0 |
| `github.com/lib/pq` | v1.12.3 (PostgreSQL driver) |
| `github.com/redis/go-redis/v9` | v9.23.0 |

### Exposed Ports
- **8080** (HTTP server, configurable via `PORT` env)

### Environment Variables
| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `PORT` | `8080` | No | HTTP listen port |
| `LOG_DIR` | `/app/logs` | No | Writable directory for error.log |
| `DB_DRIVER` | `postgres` | No | database/sql driver |
| `DB_PATH` | — | **Yes** | Driver-specific DSN (e.g., `postgres://user:pass@host:5432/db?sslmode=disable`) |

### Deploy Scripts
- **Dockerfile:** Multi-stage build at `/c/Projects/MugikoGO/Dockerfile`
- **Makefile:** Local dev + Docker migration targets
- **Referenced in:** `/c/Projects/MugikoDeploy/scripts/docker-compose.yml` (as `mynameishieu2k5/mugiko-api-layer:lastest`)

---

## 2. Mugiko Frontend

**Root Directory:** `/c/Projects/MugikoFrontend/`

### Key Subdirectories
| Path | Purpose |
|------|---------|
| `src/` | Main React application source |
| `packages/` | Monorepo workspaces (`common`, `subtitle`, `webnovel`, `ai`) |
| `dist/` | Build output (gitignored) |
| `public/` | Static assets served directly |
| `node_modules/` | Dependencies (gitignored) |
| `decks/`, `lookup/`, `subtitle/`, `webnovel/`, `ai/` | Feature directories |
| `doc/` | Documentation |

### Build System
- **Package Manager:** npm (with workspaces)
- **Build Tool:** Vite 6.3.0 + TypeScript 5.8.0
- **Dockerfile:** Multi-stage (node:24-alpine build → node:24-alpine runtime)
- **Scripts:** `dev`, `build`, `typecheck`, `preview`, `start`

### Runtime Dependencies
| Dependency | Version |
|------------|---------|
| `react` | ^19.1.0 |
| `react-dom` | ^19.1.0 |

### Dev Dependencies
| Dependency | Version |
|------------|---------|
| `@vitejs/plugin-react` | ^4.4.0 |
| `typescript` | ^5.8.0 |
| `vite` | ^6.3.0 |
| `@types/node` | ^26.6.5 |
| `@types/react` | ^19.1.0 |
| `@types/react-dom` | ^19.1.0 |

### Exposed Ports
- **3000** (HTTP via `serve -s dist -l 3000`, configurable)

### Environment Variables
| Variable | Example | Required | Description |
|----------|---------|----------|-------------|
| (See `.env.example`) | — | No | Frontend config (Vite env vars prefixed with `VITE_`) |

### Deploy Scripts
- **Dockerfile:** `/c/Projects/MugikoFrontend/Dockerfile`
- **Referenced in:** `/c/Projects/MugikoDeploy/scripts/docker-compose.yml` (as `mynameishieu2k5/mugiko-frontend:lastest`)

---

## 3. LLM Server

**Root Directory:** `/c/Projects/llm_server/`

### Key Subdirectories
| Path | Purpose |
|------|---------|
| `src/` | Python application source |
| `src/common/` | Shared utilities (db, redis) |
| `src/models.py` | Pydantic models |
| `src/config.py` | Configuration (pydantic-settings) |
| `src/nim_client.py` | NVIDIA NIM API client |
| `src/listener.py` | Redis stream listener |
| `src/processor.py` | Job processing logic |
| `src/repository.py` | Database operations |
| `src/main.py` | Application entry point |
| `migrations/` | SQL migrations |
| `deploy/` | Deployment artifacts |
| `deploy/docker/` | Dockerfile + docker-compose.yml |
| `deploy/alembic/` | Alembic migrations |
| `deploy/run/`, `deploy/setup/` | Runtime scripts |

### Build System
- **Language:** Python 3.12
- **Package Manager:** pip
- **Dockerfile:** Two variants:
  - `/c/Projects/llm_server/Dockerfile` (simple, single-stage)
  - `/c/Projects/llm_server/deploy/docker/Dockerfile` (multi-stage builder → production)
- **Docker Compose:** `/c/Projects/llm_server/deploy/docker/docker-compose.yml` (standalone stack with postgres, redis, sequin)

### Runtime Dependencies
| Dependency | Version |
|------------|---------|
| `redis` | >=5.0 |
| `psycopg2-binary` | >=2.9 |
| `python-dotenv` | >=1.0 |
| `requests` | >=2.32 |
| `pydantic` | >=2.0 |
| `pydantic-settings` | >=2.0 |

### Exposed Ports
- **None directly** (communicates via Redis streams + PostgreSQL)
- **Health check:** Python self-check (no HTTP port)

### Environment Variables
| Variable | Example | Required | Description |
|----------|---------|----------|-------------|
| `DATABASE_URL` | `postgresql://postgres:***@postgres:5432/mugiko` | **Yes** | PostgreSQL DSN |
| `REDIS_URL` | `redis://redis:6379/0` | **Yes** | Redis connection |
| `NVIDIA_API_KEYS_FILE` | `/app/nim.txt` | **Yes** | Path to NIM API keys file |
| `LLM_CONSUMER_GROUP` | `llm-workers` | No | Redis consumer group |
| `LLM_CONSUMER_NAME` | `worker-1` | No | Consumer name |
| `LLM_INPUT_STREAM` | `conversation_messages` | No | Input stream key |
| `LLM_JOBS_STREAM` | `llm_jobs` | No | Jobs stream key |
| `LLM_OUTPUT_STREAM` | `llm_responses` | No | Output stream key |
| `LLM_READ_BLOCK_MS` | `5000` | No | Redis XREAD block timeout |
| `LLM_CLAIM_IDLE_MS` | `300000` | No | Claim idle timeout |
| `LLM_STREAM_MAXLEN` | `10000` | No | Stream max length |
| `NVIDIA_NIM_BASE_URL` | `https://integrate.api.nvidia.com/v1` | No | NIM API base URL |
| `NVIDIA_NIM_MODEL` | `deepseek-ai/deepseek-v4.1-flash` | No | Model identifier |
| `NVIDIA_NIM_TEMPERATURE` | `0.2` | No | Sampling temperature |
| `NVIDIA_NIM_MAX_TOKENS` | `4096` | No | Max tokens |
| `NVIDIA_NIM_TIMEOUT_SECONDS` | `120` | No | Request timeout |
| `LLM_POLL_INTERVAL_MS` | `2000` | No | Poll interval |
| `LLM_MAX_CONCURRENT_JOBS` | `10` | No | Max concurrent jobs |

### Deploy Scripts
- **Dockerfile (simple):** `/c/Projects/llm_server/Dockerfile`
- **Dockerfile (multi-stage):** `/c/Projects/llm_server/deploy/docker/Dockerfile`
- **docker-compose.yml:** `/c/Projects/llm_server/deploy/docker/docker-compose.yml` (standalone stack)
- **Referenced in:** `/c/Projects/MugikoDeploy/scripts/docker-compose.yml` (builds from `../../llm_server` context)
- **Referenced in:** `/c/Projects/Mugiko/docker-compose.yml` (builds from `./src/llm` context)

---

## 4. Mugiko Deploy (Infrastructure)

**Root Directory:** `/c/Projects/MugikoDeploy/`

### Key Subdirectories
| Path | Purpose |
|------|---------|
| `scripts/` | Main deployment scripts |
| `scripts/envs/` | Environment files |
| `scripts/sql/` | SQL setup + migration scripts |
| `scripts/sql/setup/` | Schema + seed SQL |
| `scripts/sql/sequin/` | Sequin CDC SQL |
| `.github/` | GitHub workflows |

### Build System
- **Primary:** Docker Compose orchestration
- **No application code** — infrastructure only

### Key Files
| File | Purpose |
|------|---------|
| `scripts/docker-compose.yml` | Full stack: postgres, redis, sequin, api, frontend, work-server, llm_server |
| `scripts/playground.yml` | Sequin CDC configuration |
| `scripts/nginx.conf` | Nginx reverse proxy (referenced in Mugiko/docker-compose.yml) |

### Services Defined (in `scripts/docker-compose.yml`)
| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| `postgres` | `postgres:15-alpine` | 5432 | Primary database |
| `sequin_redis` | `redis:7-alpine` | 6379 | Redis for Sequin + app |
| `sequin` | `sequin/sequin:latest` | 7376 | CDC from Postgres → Redis |
| `api` | `mynameishieu2k5/mugiko-api-layer:lastest` | 8080 | Go backend API |
| `frontend` | `mynameishieu2k5/mugiko-frontend:lastest` | 3000→80 | React frontend |
| `work-server` | `mynameishieu2k5/mugiko-work-server:lastest` | — | Subtitle/worker processor |
| `llm_server` | Build from `../../llm_server` | — | LLM inference worker |

### Network
- **External network:** `scripts_default` (shared across all services)

### Volumes
- `postgres_data` — PostgreSQL persistence
- `redis_data` — Redis persistence

---

## 5. Mugiko Web Server (Unified Monorepo)

**Root Directory:** `/c/Projects/Mugiko/`

> **Note:** This appears to be a unified monorepo consolidating the other projects. It contains `src/` with sub-projects and a top-level `docker-compose.yml` for local development.

### Key Subdirectories
| Path | Purpose |
|------|---------|
| `src/backend/` | Go backend (copy of MugikoGO) |
| `src/frontend/` | React frontend (copy of MugikoFrontend) |
| `src/llm/` | LLM server (copy of llm_server) |
| `src/workers/` | Work server (copy of MugikoWorkServer) |
| `scripts/` | Deployment scripts (copy of MugikoDeploy/scripts) |

### Build System
- **Primary:** Docker Compose (`/c/Projects/Mugiko/docker-compose.yml`)
- **Each sub-project** has its own Dockerfile

### Docker Compose Services (from `/c/Projects/Mugiko/docker-compose.yml`)
| Service | Build Context | Dockerfile | Ports | Purpose |
|---------|---------------|------------|-------|---------|
| `postgres` | — | — | 5432 | Database |
| `sequin_redis` | — | — | 6379 | Redis |
| `sequin` | — | — | 7376 | CDC |
| `api` | `./src/backend` | `Dockerfile` | expose 8080 | Go API |
| `frontend` | `./src/frontend` | `Dockerfile` | expose 3000 | React app |
| `nginx` | — | `nginx:alpine` | 3000:80 | Reverse proxy |
| `work-server` | `./src/workers` | `Dockerfile` | — | Worker |
| `llm_server` | `./src/llm` | `Dockerfile` | — | LLM worker |

### Environment Variables (Key)
- All services reference `postgres` and `sequin_redis` by container name
- `nginx` proxies `frontend` (port 80) and `api` (port 8080)
- Secrets (DB passwords, NIM keys) use `***` placeholders in compose — expected to be injected via env files or runtime

### Deploy Scripts
- **docker-compose.yml:** `/c/Projects/Mugiko/docker-compose.yml` (local dev stack with nginx)
- **Scripts dir:** `/c/Projects/Mugiko/scripts/` (copied from MugikoDeploy)

---

## 6. MugikoWorkServer (Worker/Subtitle Processor)

**Root Directory:** `/c/Projects/MugikoWorkServer/`

> **Note:** Referenced as a separate project but also copied into `Mugiko/src/workers/`. The `nim.txt` file (NVIDIA API keys) lives here and is mounted into containers.

### Key Subdirectories
| Path | Purpose |
|------|---------|
| `src/` | Python application source |
| `src/common/` | Shared utilities |
| `src/llm/` | LLM-related worker code |
| `src/subtitle/` | Subtitle processing |
| `doc/` | Documentation |

### Build System
- **Language:** Python 3.12
- **Package Manager:** pip
- **Dockerfile:** `/c/Projects/MugikoWorkServer/Dockerfile` (single-stage python:3.12-slim)

### Runtime Dependencies
| Dependency | Version |
|------------|---------|
| `redis` | >=5.0 |
| `psycopg2-binary` | >=2.9 |
| `yt-dlp` | >=2024.12.13 |
| `python-dotenv` | >=1.0 |
| `janome` | >=0.5 (Japanese tokenizer) |
| `requests` | >=2.32 |

### Exposed Ports
- **None** (worker process, communicates via Redis streams + PostgreSQL)

### Environment Variables
| Variable | Example | Required | Description |
|----------|---------|----------|-------------|
| `DATABASE_URL` | `postgresql://postgres:***@postgres:5432/mugiko` | **Yes** | PostgreSQL DSN |
| `REDIS_URL` | `redis://sequin_redis:6379/0` | **Yes** | Redis connection |
| `SUBTITLE_STREAM` | `subtitle_queue` | No | Redis stream for subtitle jobs |
| `CONSUMER_GROUP` | `subtitle-workers` | No | Consumer group |
| `CONSUMER_NAME` | `worker-1` | No | Consumer name |
| `READ_BLOCK_MS` | `2000` | No | XREAD block timeout |
| `CLAIM_IDLE_MS` | `300000` | No | Claim idle timeout |
| `SUBTITLE_CACHE_TTL_SECONDS` | `604800` | No | Cache TTL (7 days) |
| `STATUS_STREAM` | `subtitle_status` | No | Status stream key |
| `STATUS_STREAM_MAXLEN` | `10000` | No | Status stream max length |
| `NVIDIA_API_KEYS_FILE` | `nim.txt` | **Yes** | Path to NIM keys (mounted) |
| `NVIDIA_NIM_BASE_URL` | `https://integrate.api.nvidia.com/v1` | No | NIM API base |
| `NVIDIA_NIM_MODEL` | `nvidia/nemotron-3-ultra-550b-a55b` | No | Model |
| `NVIDIA_NIM_TEMPERATURE` | `0.2` | No | Temperature |
| `NVIDIA_NIM_MAX_TOKENS` | `4096` | No | Max tokens |
| `NVIDIA_NIM_TIMEOUT_SECONDS` | `120` | No | Timeout |
| `LLM_POLL_INTERVAL_MS` | `2000` | No | LLM poll interval |
| `LLM_STALE_PROCESSING_SECONDS` | `900` | No | Stale threshold |
| `LLM_STATUS_STREAM` | `llm_status` | No | LLM status stream |
| `LLM_STATUS_STREAM_MAXLEN` | `10000` | No | LLM status max len |

### Deploy Scripts
- **Dockerfile:** `/c/Projects/MugikoWorkServer/Dockerfile`
- **Referenced in:** `/c/Projects/MugikoDeploy/scripts/docker-compose.yml` (as `mynameishieu2k5/mugiko-work-server:lastest`)
- **Referenced in:** `/c/Projects/Mugiko/docker-compose.yml` (build from `./src/workers`)
- **Key file:** `nim.txt` (NVIDIA API keys) — mounted at runtime from this repo

---

## Summary: Project Relationships

```
MugikoGO (Go backend)          → Copied to →  Mugiko/src/backend/
MugikoFrontend (React)         → Copied to →  Mugiko/src/frontend/
llm_server (Python LLM worker) → Copied to →  Mugiko/src/llm/
MugikoWorkServer (Python worker) → Copied to → Mugiko/src/workers/
MugikoDeploy (Infrastructure)  → Copied to →  Mugiko/scripts/
```

### Deployment Variants
| Compose File | Use Case | Key Difference |
|--------------|----------|----------------|
| `MugikoDeploy/scripts/docker-compose.yml` | Production-like | Uses pre-built images (`mynameishieu2k5/...:lastest`), external network `scripts_default` |
| `llm_server/deploy/docker/docker-compose.yml` | LLM standalone | Self-contained stack with own postgres/redis/sequin |
| `Mugiko/docker-compose.yml` | Local dev | Builds from source, includes nginx reverse proxy on port 3000 |

### Shared Infrastructure (from MugikoDeploy)
- **PostgreSQL:** Port 5432, DB `mugiko`, logical replication enabled for Sequin
- **Redis:** Port 6379, AOF enabled, used by Sequin + all workers
- **Sequin:** Port 7376, CDC from Postgres → Redis streams, config via `playground.yml`
- **Network:** `scripts_default` (external, shared)

### Critical Runtime Files (Not in Images)
| File | Source | Mounted Into |
|------|--------|--------------|
| `nim.txt` | `/c/Projects/MugikoWorkServer/nim.txt` | `work-server`, `llm_server` containers |
| SQL migrations | `MugikoDeploy/scripts/sql/` | postgres initdb, migration jobs |
| Sequin config | `MugikoDeploy/scripts/playground.yml` | `sequin` container |
| Nginx config | `MugikoDeploy/scripts/nginx.conf` | `nginx` container (Mugiko compose only) |

---

## Verification Checklist

- [x] All 5 primary projects located and scanned
- [x] Root paths documented
- [x] Key subdirectories listed
- [x] Build systems identified (Go modules, npm workspaces, pip, Docker)
- [x] Runtime dependencies captured
- [x] Exposed ports documented
- [x] Environment variables catalogued
- [x] Dockerfiles and docker-compose files referenced
- [x] Project relationships and copy/mapping structure documented
- [x] Shared infrastructure (postgres, redis, sequin, network) documented