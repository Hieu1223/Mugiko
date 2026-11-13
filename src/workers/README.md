# MugikoWorkServer

Subtitle worker (Python). Consumes job messages from Redis and executes them
through a fixed five-layer pipeline. The LLM worker has been moved to a
separate Go service at `src/llm-worker/`; this worker is **subtitle-only**.

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

**Important:** Progress is no longer published directly by this worker. Every
DB status write is captured by Sequin CDC, routed to `subtitle_progress`, and
consumed by the Go cache updater which writes `subtitle:progress:<id>` with a
24h TTL and publishes via Pub/Sub.

Two services exist: **YouTube → Japanese** (`youtube_ja`) and
**YouTube → Vietnamese** (`youtube_vi`), both via yt-dlp in YouTube's native
**json3** format — JSON in, JSON out. The processor tokenizes Japanese cues
with Janome and splits Vietnamese cues into whitespace-delimited words, then
stores each token as `{surface, hiragana}` — exactly two fields. Crawled
subtitles are **cached in Redis** (see provider, below), so repeated jobs for
the same video skip yt-dlp entirely.

## Layout

```
src/
├── main.py                    # entrypoint: wiring, registry sync, run (subtitle only)
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
recovered later via `XAUTOCLAIM`.

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

For Vietnamese, use `service_key = 'youtube_vi'` in the INSERT and
`service youtube_vi` in the XADD.

Verify:

```sql
SELECT status FROM subtitles WHERE id = '<uuid>';          -- completed
SELECT count(*) FROM subtitle_segments WHERE subtitle_id = '<uuid>';
```

## Subtitle progress (via Sequin CDC + cache updater)

Every status transition on `subtitles` is captured by Sequin CDC, routed to
the `subtitle_progress` stream, and consumed by the Go cache updater which
writes `subtitle:progress:<id>` (JSON snapshot, 24h TTL) and publishes via
Pub/Sub on the same key. This worker no longer publishes status directly —
progress is derived from DB writes.

## Status flow & guarantees

- `queued → processing → completed | failed`
- At-least-once delivery: messages are XACKed only after the orchestrator
  finishes; crashed or unhandled messages stay pending and are reclaimed after
  `CLAIM_IDLE_MS`.
- Handlers are idempotent: already-`completed` jobs are skipped on redelivery,
  and segment replaces delete-then-insert in one transaction.
- Job-level failures (`NoSubtitlesAvailable`, unknown provider/service, invalid
  job id, malformed message) are recorded on the job and acknowledged — a
  poison message never wedges the group.
- Stale-job recovery: on a Redis socket timeout (and at worker startup), the
  worker scans PostgreSQL for `queued`/`processing` rows older than
  `RECOVERY_STALE_SECONDS`, claims them atomically (`FOR UPDATE SKIP LOCKED`),
  and reruns them through the pipeline. `failed` rows are left terminal and are
  not retried.

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
