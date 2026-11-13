# manga-server

Standalone Go manga server backed by an integrated SQLite database.

It loads manga and chapter data from JSON files (see `docs/`), stores them in
SQLite, and exposes a read-only paginated HTTP API with searching and tag
filtering. No authentication.

## Run

```powershell
# Import sample data then serve
cd src/manga-server
go run . serve --db manga.db --addr :8090 `
  --manga ../../docs/1.json `
  --chapters ../../docs/0.json

# Serve only (data already imported)
go run . serve --db manga.db --addr :8090 --serve-only

# Import only, then exit
go run . import --db manga.db --manga ../../docs/1.json --chapters ../../docs/0.json
```

Environment equivalents: `MANGA_ADDR`, `MANGA_DB_PATH`, `MANGA_MANGA_FILE`, `MANGA_CHAPTER_FILE`.

## Endpoints

```
GET  /health
GET  /api/v1/builtin-provider/info
GET  /api/v1/builtin-provider/tags
GET  /api/v1/builtin-provider/manga
GET  /api/v1/builtin-provider/manga/{id_or_slug}
GET  /api/v1/builtin-provider/manga/{id_or_slug}/chapters
GET  /api/v1/builtin-provider/chapters?manga_id={id_or_slug}
GET  /api/v1/builtin-provider/chapters/{chapter_id}
GET  /api/v1/builtin-provider/chapters/{chapter_id}/pages
```

### Manga list filters

- `q` — search title / alternative titles / description / tag names
- `tags` — comma-separated tag slugs (any category)
- `genre`, `author`, `artist`, `status`, `type` — category shortcuts
- `year`, `min_score`
- `sort` — `updated_at` (default), `created_at`, `title`, `score`, `views`, `released`
- `order` — `asc` | `desc`
- `page` / `page_size` (max 100)

Responses are paginated: `{ items, page, page_size, total, total_pages }`.

## Build

```powershell
go build ./...
go test ./...
go vet ./...
```
