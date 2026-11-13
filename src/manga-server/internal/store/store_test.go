package store

import (
	"database/sql"
	"path/filepath"
	"testing"
	"time"

	"mugiko/manga-server/internal/sqlite"
)

func openTestDB(t *testing.T, path string) *sql.DB {
	db, err := sqlite.Open(path)
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	if err := sqlite.Migrate(db); err != nil {
		db.Close()
		t.Fatalf("migrate db: %v", err)
	}
	return db
}

func TestUpsertAndListManga(t *testing.T) {
	dir := t.TempDir()
	db := openTestDB(t, filepath.Join(dir, "test.db"))
	defer db.Close()
	r := New(db)

	m1 := &Manga{Slug: "one", Title: "One", Score: 4.5, Views: 100, UpdatedAt: time.Now().Add(-time.Hour)}
	m2 := &Manga{Slug: "two", Title: "Two", Score: 3.0, Views: 200}
	if err := r.UpsertManga(m1); err != nil {
		t.Fatalf("upsert m1: %v", err)
	}
	if err := r.UpsertManga(m2); err != nil {
		t.Fatalf("upsert m2: %v", err)
	}

	got, total, err := r.ListManga(MangaFilter{Sort: "views", Order: "desc", Page: 1, PageSize: 10})
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if total != 2 {
		t.Fatalf("expected total 2, got %d", total)
	}
	if len(got) != 2 {
		t.Fatalf("expected 2 items, got %d", len(got))
	}
	if got[0].Slug != "two" {
		t.Fatalf("expected first by views desc to be 'two', got %s", got[0].Slug)
	}

	minScore := 4.0
	filt, total2, err := r.ListManga(MangaFilter{MinScore: &minScore, Page: 1, PageSize: 10})
	if err != nil {
		t.Fatalf("list filter: %v", err)
	}
	if total2 != 1 || filt[0].Slug != "one" {
		t.Fatalf("expected only 'one' above score 4, got %d %v", total2, filt)
	}
}

func TestMangaPagination(t *testing.T) {
	dir := t.TempDir()
	db := openTestDB(t, filepath.Join(dir, "test.db"))
	defer db.Close()
	r := New(db)

	for i := 1; i <= 25; i++ {
		slug := "manga-" + string(rune('0'+i/10%10)) + string(rune('0'+i%10))
		if err := r.UpsertManga(&Manga{Slug: slug, Title: "T" + slug, Score: float64(i), Views: i}); err != nil {
			t.Fatalf("upsert %d: %v", i, err)
		}
	}
	page1, total, err := r.ListManga(MangaFilter{Page: 1, PageSize: 10})
	if err != nil {
		t.Fatalf("list: %v", err)
	}
	if total != 25 {
		t.Fatalf("expected total 25, got %d", total)
	}
	if len(page1) != 10 {
		t.Fatalf("expected 10 on page 1, got %d", len(page1))
	}
	_, total2, err := r.ListManga(MangaFilter{Page: 3, PageSize: 10})
	if err != nil {
		t.Fatalf("list page3: %v", err)
	}
	if total2 != 25 {
		t.Fatalf("expected total 25 on page3, got %d", total2)
	}
}

func TestTags(t *testing.T) {
	dir := t.TempDir()
	db := openTestDB(t, filepath.Join(dir, "test.db"))
	defer db.Close()
	r := New(db)

	t1, err := r.GetOrCreateTag("Action", "action", "genre")
	if err != nil {
		t.Fatalf("tag1: %v", err)
	}
	t2, err := r.GetOrCreateTag("Action", "action", "genre")
	if err != nil {
		t.Fatalf("tag2 dedupe: %v", err)
	}
	if t1.ID != t2.ID {
		t.Fatal("expected deduped tag to return same id")
	}
	manga := &Manga{Slug: "manga-1", Title: "Manga 1"}
	if err := r.UpsertManga(manga); err != nil {
		t.Fatalf("upsert manga: %v", err)
	}
	if err := r.LinkMangaTag(manga.ID, t1.ID); err != nil {
		t.Fatalf("link: %v", err)
	}
	mtags, err := r.GetMangaTags(manga.ID)
	if err != nil {
		t.Fatalf("get tags: %v", err)
	}
	if len(mtags) != 1 || mtags[0].Slug != "action" {
		t.Fatalf("expected 1 tag action, got %+v", mtags)
	}
	list, total, err := r.ListTags(TagFilter{Category: "genre", Page: 1, PageSize: 10})
	if err != nil {
		t.Fatalf("list tags: %v", err)
	}
	if total != 1 || list[0].Name != "Action" {
		t.Fatalf("expected 1 genre tag Action, got %d %+v", total, list)
	}
}

func TestChapterCRUD(t *testing.T) {
	dir := t.TempDir()
	db := openTestDB(t, filepath.Join(dir, "test.db"))
	defer db.Close()
	r := New(db)

	m := &Manga{Slug: "manga-x", Title: "Manga X"}
	if err := r.UpsertManga(m); err != nil {
		t.Fatalf("upsert manga: %v", err)
	}

	c := &Chapter{MangaID: m.ID, SourceIndex: 1, Number: "1", Title: "Chapter 1", PageCount: 3,
		PublishedAt: time.Now(), SourceURL: "http://example.com/ch1"}
	if err := r.UpsertChapter(c); err != nil {
		t.Fatalf("upsert chapter: %v", err)
	}
	if err := r.InsertPage(&Page{ChapterID: c.ID, Idx: 0, URL: "p1"}); err != nil {
		t.Fatalf("insert page: %v", err)
	}
	if err := r.InsertPage(&Page{ChapterID: c.ID, Idx: 1, URL: "p2"}); err != nil {
		t.Fatalf("insert page: %v", err)
	}
	if err := r.UpdateChapterPageCount(c.ID, 2); err != nil {
		t.Fatalf("update count: %v", err)
	}

	got, err := r.GetChapter(c.ID)
	if err != nil {
		t.Fatalf("get chapter: %v", err)
	}
	if got.Number != "1" {
		t.Fatalf("expected number 1, got %s", got.Number)
	}
	pages, err := r.ListChapterPages(c.ID)
	if err != nil {
		t.Fatalf("list pages: %v", err)
	}
	if len(pages) != 2 {
		t.Fatalf("expected 2 pages, got %d", len(pages))
	}
	chaps, total, err := r.ListChapters(m.ID, ChapterFilter{Page: 1, PageSize: 10})
	if err != nil {
		t.Fatalf("list chapters: %v", err)
	}
	if total != 1 || len(chaps) != 1 {
		t.Fatalf("expected 1 chapter, got %d %+v", total, chaps)
	}
}
