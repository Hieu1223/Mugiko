# MugikoWorkServer

Worker process with two background threads:

- **Subtitle worker** — consumes job messages from Redis and executes them
  through a fixed five-layer pipeline.
- **LLM worker** — polls the `llm_jobs` table for queued jobs and executes them
  through NVIDIA NIM's OpenAI-compatible chat completions API.

The subtitle pipeline:

```
Redis stream
    │  XREADGROUP (consumer group, at-least-once)
Layer 1  listener       → parses nothing but consumes stream, calls orchestrator
Layer 2  orchestrator   → routes job, tracks status, handles failures (only caller of 3–5)
Layer 3  provider       → registered via @provider/@service decorators, fetches raw data
Layer 4  processor      → pure transform (json3 → segment rows)
Layer 5  persistence    → PostgreSQL writes (idempotent)
```

Providers and processors never call anything. The listener only knows the
orchestrator. A one-time bootstrap (startup registry sync → DB) is wired in
`src/main.py`.

Currently one service exists: **YouTube → Japanese subtitles** (`youtube_ja`)
via yt-dlp in YouTube's native **json3** format — JSON in, JSON out. The
processor **tokenizes** each cue (Janome morphological analysis) and stores
each word as `{surface, hiragana}` — exactly two fields. Crawled subtitles
are **cached in Redis** (see provider, below), so repeated jobs for the same
video skip yt-dlp entirely.

## Layout

```
src/
├── main.py                    # entrypoint: wiring, registry sync, run
├── config.py                  # env config (see .env.example)
├── logging_setup.py
├── listener.py                # layer 1: consumer group + XACK + reclaim
│                              #   (runs indefinitely in its own background thread)
├── orchestrator.py            # layer 2: routes, status flow, failure policy
├── providers/
│   ├── registry.py            # generic @provider / @service decorator registry
│   ├── cache.py               # Redis cache for crawled artifacts (hit skips yt-dlp)
│   └── youtube.py             # "YouTube" provider — yt-dlp json3 download
├── processors/
│   └── json3.py               # json3 → tokenized segments ({surface, hiragana})
├── persistence/
│   ├── db.py                  # psycopg2 + transaction helper
│   ├── subtitle_repo.py       # status updates, idempotent segment writes
│   └── registry_sync.py       # startup DB mirror of the decorator registry
├── subtitle/interface.py      # shared TypedDict contracts between layers
└── common/
    ├── registry.py            # deprecated shim → src/providers/registry.py
    └── threads.py             # named background-thread wrapper for listeners
```

## Run

```powershell
pip install -r requirements.txt
copy .env.example .env      # fill in DATABASE_URL
# PostgreSQL schema applied once: doc/schema.sql
python -m src.main
```

Startup: syncs the middleware registry into `subtitle_providers` /
`subtitle_provider_services`, creates the consumer group on the stream
if missing, reclaims pending messages from crashed consumers, then loops.

`src/main.py` starts each service listener as a **daemon background thread**
(`src/common/threads.py`) that blocks on its Redis stream indefinitely; the
main thread just keeps the process alive. Ctrl+C asks listeners to stop and
joins them for up to `READ_BLOCK_MS + 5s`; unacknowledged messages are
recovered later via `XAUTOCLAIM`. Adding a future service means constructing
one more listener and appending one more `WorkerThread`.

## Smoke test (end to end)

Start the worker first (it creates the DB provider rows and the consumer
group), then in `psql`:

```sql
INSERT INTO users (user_id, auth_type, auth_id)
VALUES ('test-user', 'password', 'test-user')
ON CONFLICT DO NOTHING;

INSERT INTO subtitles (id, video_id, video_url, provider_id, service_id, created_by, status)
SELECT gen_random_uuid(), 'dQw4w9WgXcQ',
       'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
       p.id, s.id, 'test-user', 'queued'
FROM subtitle_providers p, subtitle_provider_services s
WHERE p.name = 'YouTube' AND s.service_key = 'youtube_ja'
RETURNING id;
```

Then publish the job (paste the returned id):

```
redis-cli> XADD subtitle_queue * id <returned-uuid> service youtube_ja video_url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" provider YouTube
```

Verify:

```sql
SELECT status FROM subtitles WHERE id = '<uuid>';          -- completed
SELECT count(*) FROM subtitle_segments WHERE subtitle_id = '<uuid>';
```

## Subtitle status stream

Every status transition is also published to the Redis stream configured by
`STATUS_STREAM` (default `subtitle_status`) as `{id, status}`. The API layer's
SSE endpoint reads this stream. Publishing is best-effort: a Redis failure is
logged and never fails the subtitle job.

## LLM jobs (NVIDIA NIM)

The LLM thread polls `llm_jobs` for `queued` rows, claims one with
`FOR UPDATE SKIP LOCKED`, calls NVIDIA NIM, and writes `response`, `status`, and
`error` back to the row. Stale `processing` rows are requeued after
`LLM_STALE_PROCESSING_SECONDS`.

Every LLM status transition is also published to the Redis stream configured by
`LLM_STATUS_STREAM` (default `llm_status`) as `{id, status}`, matching the
subtitle status stream. The API layer's SSE endpoint reads this stream. A stale
job moved back to `queued` is published as `queued` too.

API keys are read from `NVIDIA_API_KEYS_FILE` (default `nim.txt`), one key per
line, and used round-robin. The key file is not committed to git. There is no
environment-key fallback; transient NIM HTTP errors are retried with the same
key.

In Docker, the key file is mounted read-only at `/app/nim.txt` rather than baked
into the image, so the same image can be pushed without exposing keys.

## Status flow & guarantees

- `queued → processing → completed | failed`
- At-least-once delivery: messages are
  [XACKed only after the orchestrator finishes](src/listener.py); crashed or
  unhandled messages stay pending and are reclaimed after `CLAIM_IDLE_MS`.
- Handlers are idempotent: already-`completed` jobs are skipped on redelivery,
  and segment replaces delete-then-insert in one transaction.
- Job-level failures (`NoSubtitlesAvailable`, unknown provider/service, invalid
  job id, malformed message) are recorded on the job and acknowledged — a
  poison message never wedges the group. The sample `OpenSubtitles` messages
  from `doc/stream_res.txt` therefore get `status='failed'` until such a
  provider is implemented.

## Subtitle cache (Redis)

`src/providers/cache.py` caches crawled artifacts in Redis so repeat jobs for
the same video skip yt-dlp entirely (cold crawl ~2s → warm hit ~0s):

- Key: `subtitle:cache:YouTube:youtube_ja:<sha256(video id)>` — URLs are
  canonicalized to their video id first, so `watch?v=` / `youtu.be` /
  `shorts` aliases of one video share one entry.
- Value: the raw json3 document (JSON text), TTL `SUBTITLE_CACHE_TTL_SECONDS`
  (default 7 days). Set the TTL to `0`-short values only for testing.
- On a Redis outage the cache degrades to a miss — crawling keeps working,
  entries are never partially written.

## Adding a new service kind (manga, webnovel, ...)

1. `src/providers/<kind>.py` — a `@provider(...)` class + per-job `@service(...)`
   methods (one service per input variant, e.g. per language).
2. `src/processors/<format>.py` — a pure transform function.
3. `src/persistence/<kind>_repo.py` — table writes.
4. `src/main.py` — import the provider module (registration side effect).
5. `src/orchestrator.py` — one `Route` entry per provider in the route table.
