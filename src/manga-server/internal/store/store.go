package store

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
)

var (
	mangaNS = uuid.NewSHA1(uuid.NameSpaceDNS, []byte("mugiko.manga-server.manga"))
	tagNS   = uuid.NewSHA1(uuid.NameSpaceDNS, []byte("mugiko.manga-server.tag"))
	chapNS  = uuid.NewSHA1(uuid.NameSpaceDNS, []byte("mugiko.manga-server.chapter"))
	pageNS  = uuid.NewSHA1(uuid.NameSpaceDNS, []byte("mugiko.manga-server.page"))
)

// ---------- models ----------

type Manga struct {
	ID             string
	SourceID       string
	Slug           string
	Title          string
	AltTitles      []string
	Description    string
	Summary        string
	SourceURL      string
	CoverURL       string
	ThumbnailURL   string
	Score          float64
	Views          int
	ReleaseYear    *int
	Serialization  string
	SearchText     string
	CreatedAt      time.Time
	UpdatedAt      time.Time
	ImportedAt     time.Time
}

type Tag struct {
	ID      string
	Name    string
	Slug    string
	Category string
}

type Chapter struct {
	ID             string
	MangaID        string
	SourceIndex    int
	Number         string
	Title          string
	SourceURL      string
	PublishedAt    time.Time
	PageCount      int
	PagesTemplate  string
	CreatedAt      time.Time
	UpdatedAt      time.Time
}

type Page struct {
	ID       string
	ChapterID string
	Idx      int
	URL      string
	Width    int
	Height   int
}

// ---------- repository ----------

type Repository struct {
	db *sql.DB
}

func New(db *sql.DB) *Repository {
	return &Repository{db: db}
}

func now() time.Time {
	return time.Now().UTC()
}

func newID(ns uuid.UUID, parts ...string) string {
	return uuid.NewMD5(ns, []byte(strings.Join(parts, ":"))).String()
}

func scanTime(v interface{}) (time.Time, error) {
	switch t := v.(type) {
	case time.Time:
		return t, nil
	case string:
		if t == "" {
			return time.Time{}, nil
		}
		return time.Parse(time.RFC3339, t)
	case []byte:
		return time.Parse(time.RFC3339, string(t))
	default:
		return time.Time{}, fmt.Errorf("unsupported time type: %T", v)
	}
}

func scanInt(v interface{}) (int, bool) {
	switch n := v.(type) {
	case int64:
		return int(n), true
	case int:
		return n, true
	case float64:
		return int(n), true
	case string:
		if n == "" {
			return 0, false
		}
		var i int
		if _, err := fmt.Sscanf(n, "%d", &i); err == nil {
			return i, true
		}
		return 0, false
	case []byte:
		var i int
		if _, err := fmt.Sscanf(string(n), "%d", &i); err == nil {
			return i, true
		}
		return 0, false
	case nil:
		return 0, false
	default:
		return 0, false
	}
}

func scanFloat(v interface{}) (float64, bool) {
	switch n := v.(type) {
	case float64:
		return n, true
	case int64:
		return float64(n), true
	case int:
		return float64(n), true
	case string:
		if n == "" {
			return 0, false
		}
		var f float64
		if _, err := fmt.Sscanf(n, "%f", &f); err == nil {
			return f, true
		}
		return 0, false
	case []byte:
		var f float64
		if _, err := fmt.Sscanf(string(n), "%f", &f); err == nil {
			return f, true
		}
		return 0, false
	case nil:
		return 0, false
	default:
		return 0, false
	}
}

func scanString(v interface{}) string {
	switch s := v.(type) {
	case string:
		return s
	case []byte:
		return string(s)
	case nil:
		return ""
	default:
		return fmt.Sprintf("%v", s)
	}
}

// ---------- manga CRUD ----------

func (r *Repository) UpsertManga(m *Manga) error {
	if m.ID == "" {
		m.ID = newID(mangaNS, "manga", m.Slug)
	}
	nowT := now()
	if m.CreatedAt.IsZero() {
		m.CreatedAt = nowT
	}
	m.UpdatedAt = nowT
	m.ImportedAt = nowT

	alt, _ := json.Marshal(m.AltTitles)

	_, err := r.db.Exec(`
		INSERT INTO manga (id, source_id, slug, title, alt_titles, description, summary, source_url,
			cover_url, thumbnail_url, score, views, release_year, serialization, search_text,
			created_at, updated_at, imported_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(slug) DO UPDATE SET
			source_id=excluded.source_id,
			title=excluded.title,
			alt_titles=excluded.alt_titles,
			description=excluded.description,
			summary=excluded.summary,
			source_url=excluded.source_url,
			cover_url=excluded.cover_url,
			thumbnail_url=excluded.thumbnail_url,
			score=excluded.score,
			views=excluded.views,
			release_year=excluded.release_year,
			serialization=excluded.serialization,
			search_text=excluded.search_text,
			updated_at=excluded.updated_at,
			imported_at=excluded.imported_at
	`, m.ID, m.SourceID, m.Slug, m.Title, string(alt), m.Description, m.Summary,
		m.SourceURL, m.CoverURL, m.ThumbnailURL, m.Score, m.Views, releaseYearPtr(m.ReleaseYear),
		m.Serialization, m.SearchText, m.CreatedAt.Format(time.RFC3339), m.UpdatedAt.Format(time.RFC3339),
		m.ImportedAt.Format(time.RFC3339))
	if err != nil {
		return fmt.Errorf("upsert manga: %w", err)
	}
	return nil
}

func releaseYearPtr(y *int) interface{} {
	if y == nil {
		return nil
	}
	return *y
}

func (r *Repository) GetManga(id string) (*Manga, error) {
	row := r.db.QueryRow(`
		SELECT id, source_id, slug, title, alt_titles, description, summary, source_url,
			cover_url, thumbnail_url, score, views, release_year, serialization, search_text,
			created_at, updated_at, imported_at
		FROM manga WHERE id = ?
	`, id)
	return scanManga(row)
}

func (r *Repository) GetMangaBySlug(slug string) (*Manga, error) {
	row := r.db.QueryRow(`
		SELECT id, source_id, slug, title, alt_titles, description, summary, source_url,
			cover_url, thumbnail_url, score, views, release_year, serialization, search_text,
			created_at, updated_at, imported_at
		FROM manga WHERE slug = ?
	`, slug)
	return scanManga(row)
}

func scanManga(row *sql.Row) (*Manga, error) {
	var m Manga
	var alt, created, updated, imported string
	var release interface{}
	var score interface{}
	var views interface{}
	var desc, summary, sourceURL, cover, thumb, serial, search string
	err := row.Scan(&m.ID, &m.SourceID, &m.Slug, &m.Title, &alt, &desc, &summary, &sourceURL,
		&cover, &thumb, &score, &views, &release, &serial, &search, &created, &updated, &imported)
	if err != nil {
		return nil, err
	}
	m.Description = desc
	m.Summary = summary
	m.SourceURL = sourceURL
	m.CoverURL = cover
	m.ThumbnailURL = thumb
	m.Serialization = serial
	m.SearchText = search
	if s, ok := scanFloat(score); ok {
		m.Score = s
	}
	if v, ok := scanInt(views); ok {
		m.Views = v
	}
	if y, ok := scanInt(release); ok {
		m.ReleaseYear = &y
	}
	_ = json.Unmarshal([]byte(alt), &m.AltTitles)
	if t, err := scanTime(created); err == nil {
		m.CreatedAt = t
	}
	if t, err := scanTime(updated); err == nil {
		m.UpdatedAt = t
	}
	if t, err := scanTime(imported); err == nil {
		m.ImportedAt = t
	}
	return &m, nil
}

// ---------- list manga ----------

type MangaFilter struct {
	Q         string
	Tags      []string
	Genre     string
	Author    string
	Artist    string
	Status    string
	Type      string
	Year      *int
	MinScore  *float64
	Sort      string
	Order     string
	Page      int
	PageSize  int
}

func tagCategoryFilter(category, val string) (string, []interface{}) {
	like := "%" + val + "%"
	return "EXISTS (SELECT 1 FROM manga_tags mt JOIN tags t ON t.id = mt.tag_id WHERE mt.manga_id = manga.id AND t.category = ? AND (t.slug LIKE ? OR t.name LIKE ?))",
		[]interface{}{category, like, like}
}

func tagAnyFilter(val string) (string, []interface{}) {
	like := "%" + val + "%"
	return "EXISTS (SELECT 1 FROM manga_tags mt JOIN tags t ON t.id = mt.tag_id WHERE mt.manga_id = manga.id AND (t.slug LIKE ? OR t.name LIKE ?))",
		[]interface{}{like, like}
}

func (r *Repository) ListManga(f MangaFilter) ([]*Manga, int, error) {
	if f.Page < 1 {
		f.Page = 1
	}
	if f.PageSize < 1 {
		f.PageSize = 20
	}
	if f.PageSize > 100 {
		f.PageSize = 100
	}

	where := []string{}
	args := []interface{}{}

	if f.Q != "" {
		q := "%" + strings.ToLower(f.Q) + "%"
		where = append(where, "LOWER(search_text) LIKE ?")
		args = append(args, q)
	}

	if f.Genre != "" {
		frag, a := tagCategoryFilter("genre", f.Genre)
		where = append(where, frag)
		args = append(args, a...)
	}
	if f.Author != "" {
		frag, a := tagCategoryFilter("series-author", f.Author)
		where = append(where, frag)
		args = append(args, a...)
	}
	if f.Artist != "" {
		frag, a := tagCategoryFilter("artist", f.Artist)
		where = append(where, frag)
		args = append(args, a...)
	}
	if f.Status != "" {
		frag, a := tagCategoryFilter("status", f.Status)
		where = append(where, frag)
		args = append(args, a...)
	}
	if f.Type != "" {
		frag, a := tagCategoryFilter("type", f.Type)
		where = append(where, frag)
		args = append(args, a...)
	}
	if len(f.Tags) > 0 {
		for _, tag := range f.Tags {
			frag, a := tagAnyFilter(tag)
			where = append(where, frag)
			args = append(args, a...)
		}
	}
	if f.Year != nil {
		where = append(where, "release_year = ?")
		args = append(args, *f.Year)
	}
	if f.MinScore != nil {
		where = append(where, "score >= ?")
		args = append(args, *f.MinScore)
	}

	whereSQL := ""
	if len(where) > 0 {
		whereSQL = "WHERE " + strings.Join(where, " AND ")
	}

	orderSQL := orderByManga(f.Sort, f.Order)

	countQuery := "SELECT COUNT(*) FROM manga " + whereSQL
	var total int
	if err := r.db.QueryRow(countQuery, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count manga: %w", err)
	}

	query := `
		SELECT id, source_id, slug, title, alt_titles, description, summary, source_url,
			cover_url, thumbnail_url, score, views, release_year, serialization, search_text,
			created_at, updated_at, imported_at
		FROM manga ` + whereSQL + " " + orderSQL + `
		LIMIT ? OFFSET ?
	`
	args = append(args, f.PageSize, (f.Page-1)*f.PageSize)

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("query manga: %w", err)
	}
	defer rows.Close()

	var items []*Manga
	for rows.Next() {
		var m Manga
		var alt, created, updated, imported string
		var release, score, views interface{}
		var desc, summary, sourceURL, cover, thumb, serial, search string
		err := rows.Scan(&m.ID, &m.SourceID, &m.Slug, &m.Title, &alt, &desc, &summary, &sourceURL,
			&cover, &thumb, &score, &views, &release, &serial, &search, &created, &updated, &imported)
		if err != nil {
			return nil, 0, fmt.Errorf("scan manga: %w", err)
		}
		m.Description = desc
		m.Summary = summary
		m.SourceURL = sourceURL
		m.CoverURL = cover
		m.ThumbnailURL = thumb
		m.Serialization = serial
		m.SearchText = search
		if s, ok := scanFloat(score); ok {
			m.Score = s
		}
		if v, ok := scanInt(views); ok {
			m.Views = v
		}
		if y, ok := scanInt(release); ok {
			m.ReleaseYear = &y
		}
		_ = json.Unmarshal([]byte(alt), &m.AltTitles)
		if t, err := scanTime(created); err == nil {
			m.CreatedAt = t
		}
		if t, err := scanTime(updated); err == nil {
			m.UpdatedAt = t
		}
		if t, err := scanTime(imported); err == nil {
			m.ImportedAt = t
		}
		items = append(items, &m)
	}
	if err := rows.Err(); err != nil {
		return nil, 0, fmt.Errorf("iterate manga: %w", err)
	}
	return items, total, nil
}

func orderByManga(sort, order string) string {
	desc := "ASC"
	if strings.EqualFold(order, "desc") {
		desc = "DESC"
	}
	switch strings.ToLower(sort) {
	case "title":
		return "ORDER BY title " + desc
	case "score":
		return "ORDER BY score " + desc
	case "views":
		return "ORDER BY views " + desc
	case "created_at", "created":
		return "ORDER BY created_at " + desc
	case "released", "release_year":
		return "ORDER BY release_year " + desc
	default:
		return "ORDER BY updated_at " + desc
	}
}

// ---------- tags ----------

func (r *Repository) GetOrCreateTag(name, slug, category string) (*Tag, error) {
	row := r.db.QueryRow(`SELECT id, name, slug, category FROM tags WHERE category = ? AND slug = ?`, category, slug)
	var t Tag
	var id, nameS, slugS, catS string
	err := row.Scan(&id, &nameS, &slugS, &catS)
	if err == nil {
		t.ID = id
		t.Name = nameS
		t.Slug = slugS
		t.Category = catS
		return &t, nil
	}
	if err != sql.ErrNoRows {
		return nil, fmt.Errorf("query tag: %w", err)
	}

	id = newID(tagNS, "tag", category, slug)
	_, err = r.db.Exec(`INSERT INTO tags (id, name, slug, category) VALUES (?, ?, ?, ?)`,
		id, name, slug, category)
	if err != nil {
		return nil, fmt.Errorf("insert tag: %w", err)
	}
	return &Tag{ID: id, Name: name, Slug: slug, Category: category}, nil
}

func (r *Repository) LinkMangaTag(mangaID, tagID string) error {
	_, err := r.db.Exec(`INSERT OR IGNORE INTO manga_tags (manga_id, tag_id) VALUES (?, ?)`, mangaID, tagID)
	return err
}

func (r *Repository) UpdateChapterPageCount(chapterID string, count int) error {
	_, err := r.db.Exec(`UPDATE chapters SET page_count = ? WHERE id = ?`, count, chapterID)
	if err != nil {
		return fmt.Errorf("update chapter page count: %w", err)
	}
	return nil
}

func (r *Repository) GetMangaTags(mangaID string) ([]*Tag, error) {
	rows, err := r.db.Query(`
		SELECT t.id, t.name, t.slug, t.category FROM tags t
		JOIN manga_tags mt ON mt.tag_id = t.id
		WHERE mt.manga_id = ?
		ORDER BY t.category, t.name
	`, mangaID)
	if err != nil {
		return nil, fmt.Errorf("query manga tags: %w", err)
	}
	defer rows.Close()
	var items []*Tag
	for rows.Next() {
		var t Tag
		if err := rows.Scan(&t.ID, &t.Name, &t.Slug, &t.Category); err != nil {
			return nil, err
		}
		items = append(items, &t)
	}
	return items, rows.Err()
}

func (r *Repository) ListTags(filter TagFilter) ([]*Tag, int, error) {
	if filter.Page < 1 {
		filter.Page = 1
	}
	if filter.PageSize < 1 {
		filter.PageSize = 50
	}
	if filter.PageSize > 10000 {
		filter.PageSize = 10000
	}
	where := []string{}
	args := []interface{}{}
	if filter.Category != "" {
		where = append(where, "category = ?")
		args = append(args, filter.Category)
	}
	if filter.Q != "" {
		where = append(where, "(LOWER(name) LIKE ? OR LOWER(slug) LIKE ?)")
		q := "%" + strings.ToLower(filter.Q) + "%"
		args = append(args, q, q)
	}
	whereSQL := ""
	if len(where) > 0 {
		whereSQL = "WHERE " + strings.Join(where, " AND ")
	}
	desc := "ASC"
	if strings.EqualFold(filter.Order, "desc") {
		desc = "DESC"
	}
	orderSQL := "ORDER BY name " + desc
	countQuery := "SELECT COUNT(*) FROM tags " + whereSQL
	var total int
	if err := r.db.QueryRow(countQuery, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count tags: %w", err)
	}
	query := `SELECT id, name, slug, category FROM tags ` + whereSQL + " " + orderSQL +
		` LIMIT ? OFFSET ?`
	args = append(args, filter.PageSize, (filter.Page-1)*filter.PageSize)
	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("query tags: %w", err)
	}
	defer rows.Close()
	var items []*Tag
	for rows.Next() {
		var t Tag
		if err := rows.Scan(&t.ID, &t.Name, &t.Slug, &t.Category); err != nil {
			return nil, 0, err
		}
		items = append(items, &t)
	}
	return items, total, rows.Err()
}

type TagFilter struct {
	Category string
	Q        string
	Sort     string
	Order    string
	Page     int
	PageSize int
}

// ---------- chapters ----------

func (r *Repository) UpsertChapter(c *Chapter) error {
	if c.ID == "" {
		c.ID = newID(chapNS, "chapter", c.MangaID, fmt.Sprintf("%d", c.SourceIndex))
	}
	nowT := now()
	if c.CreatedAt.IsZero() {
		c.CreatedAt = nowT
	}
	c.UpdatedAt = nowT
	_, err := r.db.Exec(`
		INSERT INTO chapters (id, manga_id, source_index, number, title, source_url,
			published_at, page_count, pages_template, created_at, updated_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(manga_id, source_index) DO UPDATE SET
			number=excluded.number,
			title=excluded.title,
			source_url=excluded.source_url,
			published_at=excluded.published_at,
			page_count=excluded.page_count,
			pages_template=excluded.pages_template,
			updated_at=excluded.updated_at
	`, c.ID, c.MangaID, c.SourceIndex, c.Number, c.Title, c.SourceURL,
		c.PublishedAt.Format(time.RFC3339), c.PageCount, c.PagesTemplate,
		c.CreatedAt.Format(time.RFC3339), c.UpdatedAt.Format(time.RFC3339))
	if err != nil {
		return fmt.Errorf("upsert chapter: %w", err)
	}
	return nil
}

func (r *Repository) DeleteChapterPages(chapterID string) error {
	_, err := r.db.Exec(`DELETE FROM pages WHERE chapter_id = ?`, chapterID)
	return err
}

func (r *Repository) InsertPage(p *Page) error {
	if p.ID == "" {
		p.ID = newID(pageNS, "page", p.ChapterID, fmt.Sprintf("%d", p.Idx))
	}
	_, err := r.db.Exec(`
		INSERT OR REPLACE INTO pages (id, chapter_id, idx, url, width, height)
		VALUES (?, ?, ?, ?, ?, ?)
	`, p.ID, p.ChapterID, p.Idx, p.URL, p.Width, p.Height)
	if err != nil {
		return fmt.Errorf("insert page: %w", err)
	}
	return nil
}

func (r *Repository) GetChapter(id string) (*Chapter, error) {
	row := r.db.QueryRow(`
		SELECT id, manga_id, source_index, number, title, source_url, published_at,
			page_count, pages_template, created_at, updated_at
		FROM chapters WHERE id = ?
	`, id)
	var c Chapter
	var pub, created, updated string
	err := row.Scan(&c.ID, &c.MangaID, &c.SourceIndex, &c.Number, &c.Title, &c.SourceURL,
		&pub, &c.PageCount, &c.PagesTemplate, &created, &updated)
	if err != nil {
		return nil, err
	}
	if t, err := scanTime(pub); err == nil {
		c.PublishedAt = t
	}
	if t, err := scanTime(created); err == nil {
		c.CreatedAt = t
	}
	if t, err := scanTime(updated); err == nil {
		c.UpdatedAt = t
	}
	return &c, nil
}

func (r *Repository) GetChapterBySlug(mangaSlug string, sourceIndex int) (*Chapter, error) {
	row := r.db.QueryRow(`
		SELECT c.id, c.manga_id, c.source_index, c.number, c.title, c.source_url, c.published_at,
			c.page_count, c.pages_template, c.created_at, c.updated_at
		FROM chapters c
		JOIN manga m ON m.id = c.manga_id
		WHERE m.slug = ? AND c.source_index = ?
	`, mangaSlug, sourceIndex)
	var c Chapter
	var pub, created, updated string
	err := row.Scan(&c.ID, &c.MangaID, &c.SourceIndex, &c.Number, &c.Title, &c.SourceURL,
		&pub, &c.PageCount, &c.PagesTemplate, &created, &updated)
	if err != nil {
		return nil, err
	}
	if t, err := scanTime(pub); err == nil {
		c.PublishedAt = t
	}
	if t, err := scanTime(created); err == nil {
		c.CreatedAt = t
	}
	if t, err := scanTime(updated); err == nil {
		c.UpdatedAt = t
	}
	return &c, nil
}

func (r *Repository) ListChapters(mangaID string, filter ChapterFilter) ([]*Chapter, int, error) {
	if filter.Page < 1 {
		filter.Page = 1
	}
	if filter.PageSize < 1 {
		filter.PageSize = 50
	}
	if filter.PageSize > 200 {
		filter.PageSize = 200
	}
	desc := "ASC"
	if strings.EqualFold(filter.Order, "desc") {
		desc = "DESC"
	}
	orderSQL := "ORDER BY source_index " + desc
	switch strings.ToLower(filter.Sort) {
	case "published_at":
		orderSQL = "ORDER BY published_at " + desc
	case "number":
		orderSQL = "ORDER BY number " + desc
	}

	countQuery := "SELECT COUNT(*) FROM chapters WHERE manga_id = ?"
	var total int
	if err := r.db.QueryRow(countQuery, mangaID).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("count chapters: %w", err)
	}

	query := `
		SELECT id, manga_id, source_index, number, title, source_url, published_at,
			page_count, pages_template, created_at, updated_at
		FROM chapters WHERE manga_id = ? ` + orderSQL + `
		LIMIT ? OFFSET ?
	`
	rows, err := r.db.Query(query, mangaID, filter.PageSize, (filter.Page-1)*filter.PageSize)
	if err != nil {
		return nil, 0, fmt.Errorf("query chapters: %w", err)
	}
	defer rows.Close()
	var items []*Chapter
	for rows.Next() {
		var c Chapter
		var pub, created, updated string
		if err := rows.Scan(&c.ID, &c.MangaID, &c.SourceIndex, &c.Number, &c.Title, &c.SourceURL,
			&pub, &c.PageCount, &c.PagesTemplate, &created, &updated); err != nil {
			return nil, 0, fmt.Errorf("scan chapter: %w", err)
		}
		if t, err := scanTime(pub); err == nil {
			c.PublishedAt = t
		}
		if t, err := scanTime(created); err == nil {
			c.CreatedAt = t
		}
		if t, err := scanTime(updated); err == nil {
			c.UpdatedAt = t
		}
		items = append(items, &c)
	}
	return items, total, rows.Err()
}

type ChapterFilter struct {
	Sort   string
	Order  string
	Page   int
	PageSize int
}

func (r *Repository) ListChapterPages(chapterID string) ([]*Page, error) {
	rows, err := r.db.Query(`
		SELECT id, chapter_id, idx, url, width, height
		FROM pages WHERE chapter_id = ?
		ORDER BY idx
	`, chapterID)
	if err != nil {
		return nil, fmt.Errorf("query pages: %w", err)
	}
	defer rows.Close()
	var items []*Page
	for rows.Next() {
		var p Page
		if err := rows.Scan(&p.ID, &p.ChapterID, &p.Idx, &p.URL, &p.Width, &p.Height); err != nil {
			return nil, err
		}
		items = append(items, &p)
	}
	return items, rows.Err()
}
