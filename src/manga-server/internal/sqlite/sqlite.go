package sqlite

import (
	"database/sql"
	"fmt"
	"time"

	_ "modernc.org/sqlite"
)

func Open(path string) (*sql.DB, error) {
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, fmt.Errorf("open sqlite: %w", err)
	}
	db.SetMaxOpenConns(1)
	if err := pingWithRetry(db); err != nil {
		db.Close()
		return nil, err
	}
	return db, nil
}

func pingWithRetry(db *sql.DB) error {
	var lastErr error
	for i := 0; i < 10; i++ {
		if err := db.Ping(); err == nil {
			return nil
		} else {
			lastErr = err
			time.Sleep(100 * time.Millisecond)
		}
	}
	return fmt.Errorf("ping sqlite: %w", lastErr)
}

const Schema = `
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS manga (
    id             TEXT PRIMARY KEY,
    source_id      TEXT,
    slug           TEXT NOT NULL UNIQUE,
    title          TEXT NOT NULL,
    alt_titles     TEXT NOT NULL DEFAULT '[]',
    description    TEXT NOT NULL DEFAULT '',
    summary        TEXT NOT NULL DEFAULT '',
    source_url     TEXT NOT NULL DEFAULT '',
    cover_url      TEXT NOT NULL DEFAULT '',
    thumbnail_url  TEXT NOT NULL DEFAULT '',
    score          REAL NOT NULL DEFAULT 0,
    views          INTEGER NOT NULL DEFAULT 0,
    release_year   INTEGER,
    serialization  TEXT NOT NULL DEFAULT '',
    search_text    TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    imported_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_manga_slug ON manga(slug);
CREATE INDEX IF NOT EXISTS ix_manga_title ON manga(title);
CREATE INDEX IF NOT EXISTS ix_manga_score ON manga(score);
CREATE INDEX IF NOT EXISTS ix_manga_views ON manga(views);
CREATE INDEX IF NOT EXISTS ix_manga_updated ON manga(updated_at);
CREATE INDEX IF NOT EXISTS ix_manga_release ON manga(release_year);
CREATE INDEX IF NOT EXISTS ix_manga_search ON manga(search_text);

CREATE TABLE IF NOT EXISTS tags (
    id        TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    slug      TEXT NOT NULL,
    category  TEXT NOT NULL,
    UNIQUE (category, slug)
);

CREATE INDEX IF NOT EXISTS ix_tags_category ON tags(category);
CREATE INDEX IF NOT EXISTS ix_tags_category_slug ON tags(category, slug);

CREATE TABLE IF NOT EXISTS manga_tags (
    manga_id TEXT NOT NULL,
    tag_id   TEXT NOT NULL,
    PRIMARY KEY (manga_id, tag_id),
    FOREIGN KEY (manga_id) REFERENCES manga(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)   REFERENCES tags(id)   ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_manga_tags_tag ON manga_tags(tag_id);

CREATE TABLE IF NOT EXISTS chapters (
    id             TEXT PRIMARY KEY,
    manga_id       TEXT NOT NULL,
    source_index   INTEGER NOT NULL,
    number         TEXT NOT NULL,
    title          TEXT NOT NULL DEFAULT '',
    source_url     TEXT NOT NULL DEFAULT '',
    published_at   TEXT NOT NULL,
    page_count     INTEGER NOT NULL DEFAULT 0,
    pages_template TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    FOREIGN KEY (manga_id) REFERENCES manga(id) ON DELETE CASCADE,
    UNIQUE (manga_id, source_index)
);

CREATE INDEX IF NOT EXISTS ix_chapters_manga ON chapters(manga_id);
CREATE INDEX IF NOT EXISTS ix_chapters_manga_index ON chapters(manga_id, source_index);
CREATE INDEX IF NOT EXISTS ix_chapters_published ON chapters(published_at);

CREATE TABLE IF NOT EXISTS pages (
    id        TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL,
    idx       INTEGER NOT NULL,
    url       TEXT NOT NULL DEFAULT '',
    width     INTEGER NOT NULL DEFAULT 0,
    height    INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
    UNIQUE (chapter_id, idx)
);

CREATE INDEX IF NOT EXISTS ix_pages_chapter ON pages(chapter_id);
CREATE INDEX IF NOT EXISTS ix_pages_chapter_idx ON pages(chapter_id, idx);
`

func Migrate(db *sql.DB) error {
	_, err := db.Exec(Schema)
	if err != nil {
		return fmt.Errorf("migrate sqlite: %w", err)
	}
	return nil
}
