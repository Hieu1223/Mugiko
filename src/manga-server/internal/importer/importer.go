package importer

import (
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode"

	"mugiko/manga-server/internal/store"
)
var (
	chapterNumRe = regexp.MustCompile(`(?i)chapter\s*([0-9]+(?:\.[0-9]+)?)`)
	numRe        = regexp.MustCompile(`[0-9]+(?:\.[0-9]+)?`)
	tagRe        = regexp.MustCompile(`<[^>]*>`)
	spaceRe      = regexp.MustCompile(`\s+`)
)

type ImportResult struct {
	Manga    int
	Tags     int
	Chapters int
	Pages    int
}

// Import loads a manga file and/or chapter file into the store.
func Import(s *store.Repository, mangaFile, chapterFile string) (*ImportResult, error) {
	res := &ImportResult{}
	if mangaFile != "" {
		r, e := importMangaPath(s, mangaFile)
		if e != nil {
			return nil, fmt.Errorf("import manga: %w", e)
		}
		res.Manga = r.Manga
		res.Tags = r.Tags
	}
	if chapterFile != "" {
		r, e := importChapterPath(s, chapterFile)
		if e != nil {
			return nil, fmt.Errorf("import chapters: %w", e)
		}
		res.Chapters = r.Chapters
		res.Pages = r.Pages
	}
	return res, nil
}

// ---------- manga ----------

type wpManga struct {
	ID          int                    `json:"id"`
	Slug        string                 `json:"slug"`
	Title       struct{ Rendered string `json:"rendered"` } `json:"title"`
	Content     struct{ Rendered string `json:"rendered"` } `json:"content"`
	Excerpt     struct{ Rendered string `json:"rendered"` } `json:"excerpt"`
	Link        string                 `json:"link"`
	Date        string                 `json:"date"`
	DateGMT     string                 `json:"date_gmt"`
	Modified    string                 `json:"modified"`
	ModifiedGMT string                 `json:"modified_gmt"`
	Featured    int                    `json:"featured_media"`
	Meta        struct {
		Meta map[string]interface{} `json:"meta"`
		Tax  []wpTax                `json:"tax"`
	} `json:"meta"`
	MangaStatus interface{} `json:"manga-status"`
	MangaType   interface{} `json:"manga-type"`
	Genre       []int       `json:"genre"`
	SeriesAuthor []int      `json:"series-author"`
	Artist      []int       `json:"artist"`
	Embedded    struct {
		FeaturedMedia []wpMedia `json:"wp:featuredmedia"`
		Terms         [][]wpTerm `json:"wp:term"`
	} `json:"_embedded"`
}

type wpTax struct {
	TermID    int    `json:"term_id"`
	Name      string `json:"name"`
	Slug      string `json:"slug"`
	Taxonomy  string `json:"taxonomy"`
	Count     int    `json:"count"`
}

type wpMedia struct {
	ID         int    `json:"id"`
	Slug       string `json:"slug"`
	SourceURL  string `json:"source_url"`
	MediaType  string `json:"media_type"`
	MimeType   string `json:"mime_type"`
}

type wpTerm struct {
	Taxonomy string `json:"taxonomy"`
	Name     string `json:"name"`
	Slug     string `json:"slug"`
}

func importMangaPath(s *store.Repository, path string) (*ImportResult, error) {
	res := &ImportResult{}
	info, err := os.Stat(path)
	if err != nil {
		return nil, err
	}
	if info.IsDir() {
		entries, err := os.ReadDir(path)
		if err != nil {
			return nil, err
		}
		sort.Slice(entries, func(i, j int) bool { return entries[i].Name() < entries[j].Name() })
		for _, e := range entries {
			if e.IsDir() || !strings.HasSuffix(strings.ToLower(e.Name()), ".json") {
				continue
			}
			name := filepath.Join(path, e.Name())
			r, e := importMangaFile(s, name)
			if e != nil {
				return nil, fmt.Errorf("file %s: %w", name, e)
			}
			res.Manga += r.Manga
			res.Tags += r.Tags
		}
		return res, nil
	}
	return importMangaFile(s, path)
}

func importMangaFile(s *store.Repository, path string) (*ImportResult, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	// Trim BOM if present
	data = bytesTrimBOM(data)

	var arr []wpManga
	var single wpManga
	if err := json.Unmarshal(data, &arr); err != nil {
		if err2 := json.Unmarshal(data, &single); err2 != nil {
			return nil, fmt.Errorf("parse json: %w (single: %v)", err, err2)
		}
		arr = []wpManga{single}
	}

	res := &ImportResult{}
	for _, m := range arr {
		mm, tags, err := mapManga(m)
		if err != nil {
			return nil, fmt.Errorf("map manga %q: %w", m.Slug, err)
		}
		if err := s.UpsertManga(mm); err != nil {
			return nil, fmt.Errorf("upsert manga %q: %w", m.Slug, err)
		}
		res.Manga++
		for _, tag := range tags {
			t, err := s.GetOrCreateTag(tag.Name, tag.Slug, tag.Category)
			if err != nil {
				return nil, fmt.Errorf("get/create tag %q: %w", tag.Name, err)
			}
			if err := s.LinkMangaTag(mm.ID, t.ID); err != nil {
				return nil, fmt.Errorf("link manga tag %q: %w", tag.Name, err)
			}
			res.Tags++
		}
	}
	return res, nil
}

func mapManga(m wpManga) (*store.Manga, []store.Tag, error) {
	title := strings.TrimSpace(m.Title.Rendered)
	slug := m.Slug
	if slug == "" {
		slug = slugify(title)
	}

	desc := stripTags(m.Content.Rendered)
	summary := stripTags(m.Excerpt.Rendered)
	if summary == "" && desc != "" {
		summary = truncate(desc, 300)
	}

	sourceURL := m.Link
	coverURL := ""
	thumbURL := ""
	if len(m.Embedded.FeaturedMedia) > 0 {
		coverURL = m.Embedded.FeaturedMedia[0].SourceURL
		thumbURL = coverURL
	}
	if thumbURL == "" {
		if v, ok := m.Meta.Meta["thumbnail"]; ok {
			if s, ok := v.(string); ok {
				thumbURL = s
			}
		}
	}
	if coverURL == "" && thumbURL != "" {
		coverURL = thumbURL
	}

	score, _ := parseFloat(m.Meta.Meta["score"])
	views, _ := parseInt(m.Meta.Meta["views"])
	var releaseYear *int
	if v, ok := parseIntPtr(m.Meta.Meta["released"]); ok {
		releaseYear = &v
	}
	serialization := str(m.Meta.Meta["serialization"])

	altTitles := []string{}
	if v, ok := m.Meta.Meta["alternative_title"]; ok {
		if s, ok := v.(string); ok && s != "" {
			for _, part := range strings.Split(s, ",") {
				p := strings.TrimSpace(part)
				if p != "" {
					altTitles = append(altTitles, p)
				}
			}
		}
	}

	searchParts := []string{strings.ToLower(title)}
	for _, a := range altTitles {
		searchParts = append(searchParts, strings.ToLower(a))
	}
	searchParts = append(searchParts, strings.ToLower(desc), strings.ToLower(summary))

	var tags []store.Tag
	seen := map[string]bool{}
	addTag := func(name, slug, category string) {
		if name == "" || slug == "" || seen[category+":"+slug] {
			return
		}
		seen[category+":"+slug] = true
		tags = append(tags, store.Tag{Name: name, Slug: slug, Category: category})
		searchParts = append(searchParts, strings.ToLower(name), strings.ToLower(slug), strings.ToLower(category))
	}

	// Prefer meta.tax (has category), fall back to embedded terms.
	for _, t := range m.Meta.Tax {
		addTag(t.Name, t.Slug, t.Taxonomy)
	}
	if len(seen) == 0 {
		for _, group := range m.Embedded.Terms {
			for _, t := range group {
				addTag(t.Name, t.Slug, t.Taxonomy)
			}
		}
	}

	// Backwards compat top-level arrays keyed by id -> name (not available here),
	// but taxonomy arrays are already captured via meta.tax.

	mm := &store.Manga{
		Slug:           slug,
		Title:          title,
		AltTitles:      altTitles,
		Description:    desc,
		Summary:        summary,
		SourceURL:      sourceURL,
		CoverURL:       coverURL,
		ThumbnailURL:   thumbURL,
		Score:          score,
		Views:          views,
		ReleaseYear:    releaseYear,
		Serialization:  serialization,
		SearchText:     spaceRe.ReplaceAllString(strings.Join(searchParts, " "), " "),
	}
	return mm, tags, nil
}

// ---------- chapters ----------

type wpChapter struct {
	Slug       string `json:"slug"`
	Index      int    `json:"index"`
	Title      string `json:"title"`
	URL        string `json:"url"`
	Date       string `json:"date"`
	PageCount  int    `json:"page_count"`
	Images     []string `json:"images"`
	Pages      struct {
		Type       string `json:"type"`
		BaseURL    string `json:"base_url"`
		PageCount  int    `json:"page_count"`
		Pattern    string `json:"pattern"`
	} `json:"pages"`
}

func importChapterPath(s *store.Repository, path string) (*ImportResult, error) {
	res := &ImportResult{}
	info, err := os.Stat(path)
	if err != nil {
		return nil, err
	}
	if info.IsDir() {
		entries, err := os.ReadDir(path)
		if err != nil {
			return nil, err
		}
		sort.Slice(entries, func(i, j int) bool { return entries[i].Name() < entries[j].Name() })
		for _, e := range entries {
			if e.IsDir() || !strings.HasSuffix(strings.ToLower(e.Name()), ".json") {
				continue
			}
			name := filepath.Join(path, e.Name())
			r, e := importChapterFile(s, name)
			if e != nil {
				return nil, fmt.Errorf("file %s: %w", name, e)
			}
			res.Chapters += r.Chapters
			res.Pages += r.Pages
		}
		return res, nil
	}
	return importChapterFile(s, path)
}

func importChapterFile(s *store.Repository, path string) (*ImportResult, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	data = bytesTrimBOM(data)

	var arr []wpChapter
	var single wpChapter
	if err := json.Unmarshal(data, &arr); err != nil {
		if err2 := json.Unmarshal(data, &single); err2 != nil {
			return nil, fmt.Errorf("parse json: %w (single: %v)", err, err2)
		}
		arr = []wpChapter{single}
	}

	res := &ImportResult{}
	for _, c := range arr {
		manga, err := s.GetMangaBySlug(c.Slug)
		if err != nil {
			if !errors.Is(err, sql.ErrNoRows) {
				return nil, fmt.Errorf("find manga %q: %w", c.Slug, err)
			}
			manga = nil
		}
		if manga == nil {
			// Create a placeholder manga so orphan chapter data is still browsable.
			manga = &store.Manga{
				Slug:        c.Slug,
				Title:       titleCase(c.Slug),
				SearchText:  strings.ToLower(c.Slug),
			}
			if err := s.UpsertManga(manga); err != nil {
				return nil, fmt.Errorf("upsert placeholder manga %q: %w", c.Slug, err)
			}
		}

		chapter := &store.Chapter{
			MangaID:     manga.ID,
			SourceIndex: c.Index,
			Number:      chapterNumber(c.Title, c.Index),
			Title:       strings.TrimSpace(c.Title),
			SourceURL:   c.URL,
			PageCount:   c.PageCount,
			PagesTemplate: buildTemplate(c.Pages.BaseURL, c.Pages.Pattern, c.PageCount),
		}
		if t, err := parseTime(c.Date); err == nil {
			chapter.PublishedAt = t
		} else {
			chapter.PublishedAt = time.Now().UTC()
		}
		if err := s.UpsertChapter(chapter); err != nil {
			return nil, fmt.Errorf("upsert chapter index %d: %w", c.Index, err)
		}

		// Replace pages
		if err := s.DeleteChapterPages(chapter.ID); err != nil {
			return nil, fmt.Errorf("delete pages: %w", err)
		}
		pageCount := 0
		urls := c.Images
		if len(urls) == 0 && c.Pages.Type == "template" && c.Pages.BaseURL != "" && c.Pages.Pattern != "" {
			count := c.Pages.PageCount
			if count <= 0 {
				count = c.PageCount
			}
			urls = templateURLs(c.Pages.BaseURL, c.Pages.Pattern, count)
		}
		for i, u := range urls {
			u = strings.TrimSpace(u)
			if u == "" {
				continue
			}
			if err := s.InsertPage(&store.Page{
				ChapterID: chapter.ID,
				Idx:       i,
				URL:       u,
			}); err != nil {
				return nil, fmt.Errorf("insert page %d: %w", i, err)
			}
			pageCount++
		}
		if pageCount > 0 {
			if err := s.UpdateChapterPageCount(chapter.ID, pageCount); err != nil {
				return nil, fmt.Errorf("update page count: %w", err)
			}
		}
		res.Chapters++
		res.Pages += pageCount
	}
	return res, nil
}

// ---------- helpers ----------

func bytesTrimBOM(data []byte) []byte {
	if len(data) >= 3 && data[0] == 0xEF && data[1] == 0xBB && data[2] == 0xBF {
		return data[3:]
	}
	return data
}

func stripTags(html string) string {
	t := tagRe.ReplaceAllString(html, " ")
	t = strings.ReplaceAll(t, "&nbsp;", " ")
	t = strings.ReplaceAll(t, "&amp;", "&")
	t = strings.ReplaceAll(t, "&lt;", "<")
	t = strings.ReplaceAll(t, "&gt;", ">")
	t = strings.ReplaceAll(t, "&quot;", "\"")
	t = strings.ReplaceAll(t, "&#39;", "'")
	t = spaceRe.ReplaceAllString(t, " ")
	return strings.TrimSpace(t)
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}

func slugify(s string) string {
	s = strings.ToLower(s)
	s = strings.ReplaceAll(s, "&", " and ")
	s = tagRe.ReplaceAllString(s, " ")
	s = strings.Map(func(r rune) rune {
		if r >= 'a' && r <= 'z' || r >= '0' && r <= '9' {
			return r
		}
		return '-'
	}, s)
	for strings.Contains(s, "--") {
		s = strings.ReplaceAll(s, "--", "-")
	}
	s = strings.Trim(s, "-")
	return s
}

func chapterNumber(title string, index int) string {
	title = strings.TrimSpace(title)
	if m := chapterNumRe.FindStringSubmatch(title); len(m) == 2 {
		return m[1]
	}
	return strconv.Itoa(index)
}

func parseTime(s string) (time.Time, error) {
	s = strings.TrimSpace(s)
	if s == "" {
		return time.Time{}, fmt.Errorf("empty")
	}
	layouts := []string{
		time.RFC3339Nano,
		time.RFC3339,
		"2006-01-02T15:04:05Z",
		"2006-01-02T15:04:05-07:00",
		"2006-01-02 15:04:05",
		"2006-01-02",
	}
	var lastErr error
	for _, layout := range layouts {
		if t, err := time.Parse(layout, s); err == nil {
			return t, nil
		} else {
			lastErr = err
		}
	}
	return time.Time{}, lastErr
}

func parseFloat(v interface{}) (float64, bool) {
	switch n := v.(type) {
	case float64:
		return n, true
	case string:
		if f, err := strconv.ParseFloat(strings.TrimSpace(n), 64); err == nil {
			return f, true
		}
	case []byte:
		if f, err := strconv.ParseFloat(strings.TrimSpace(string(n)), 64); err == nil {
			return f, true
		}
	}
	return 0, false
}

func parseInt(v interface{}) (int, bool) {
	switch n := v.(type) {
	case float64:
		return int(n), true
	case string:
		if i, err := strconv.Atoi(strings.TrimSpace(n)); err == nil {
			return i, true
		}
	case []byte:
		if i, err := strconv.Atoi(strings.TrimSpace(string(n))); err == nil {
			return i, true
		}
	}
	return 0, false
}

func parseIntPtr(v interface{}) (int, bool) {
	return parseInt(v)
}

func str(v interface{}) string {
	switch s := v.(type) {
	case string:
		return s
	case []byte:
		return string(s)
	default:
		return ""
	}
}

func buildTemplate(base, pattern string, count int) string {
	if base == "" || pattern == "" {
		return ""
	}
	u, err := url.Parse(base)
	if err != nil {
		return ""
	}
	return u.String()
}

func titleCase(s string) string {
	parts := strings.FieldsFunc(s, func(r rune) bool {
		return r == '-' || r == '_' || r == ' '
	})
	for i, p := range parts {
		if p == "" {
			continue
		}
		runes := []rune(p)
		runes[0] = unicode.ToUpper(runes[0])
		parts[i] = string(runes)
	}
	return strings.Join(parts, " ")
}

func templateURLs(base, pattern string, count int) []string {
	urls := make([]string, 0, count)
	for i := 1; i <= count; i++ {
		p := pattern
		p = strings.ReplaceAll(p, "{:01d}", fmt.Sprintf("%d", i))
		p = strings.ReplaceAll(p, "{:02d}", fmt.Sprintf("%02d", i))
		p = strings.ReplaceAll(p, "{:03d}", fmt.Sprintf("%03d", i))
		p = strings.ReplaceAll(p, "{i}", fmt.Sprintf("%d", i))
		u := strings.TrimRight(base, "/") + "/" + p
		urls = append(urls, u)
	}
	return urls
}
