package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"regexp"
	"strconv"
	"strings"
	"time"

	"mugiko/manga-server/internal/sqlite"
	"mugiko/manga-server/internal/store"
)

var (
	chapterNumRe = regexp.MustCompile(`(?i)chapter\s*([0-9]+(?:\.[0-9]+)?)`)
	numRe        = regexp.MustCompile(`[0-9]+(?:\.[0-9]+)?`)
	tagRe        = regexp.MustCompile(`<[^>]*>`)
	spaceRe      = regexp.MustCompile(`\s+`)
)

// ---------- raw merged.json structures ----------

type rawManga struct {
	ID          int                    `json:"id"`
	Slug        string                 `json:"slug"`
	Title       struct{ Rendered string `json:"rendered"` } `json:"title"`
	Content     struct{ Rendered string `json:"rendered"` } `json:"content"`
	Excerpt     struct{ Rendered string `json:"rendered"` } `json:"excerpt"`
	Link        string                 `json:"link"`
	Date        string                 `json:"date"`
	Modified    string                 `json:"modified"`
	Featured    int                    `json:"featured_media"`
	Meta        struct {
		Meta map[string]interface{} `json:"meta"`
		Tax  []rawTax               `json:"tax"`
	} `json:"meta"`
	Chapters []rawChapter `json:"chapters"`
}

type rawTax struct {
	TermID    int    `json:"term_id"`
	Name      string `json:"name"`
	Slug      string `json:"slug"`
	Taxonomy  string `json:"taxonomy"`
}

type rawChapter struct {
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

// ---------- helpers (mirror importer package) ----------

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
	case nil:
		return 0, false
	}
	return 0, false
}

func buildTemplate(baseURL, pattern string, count int) string {
	if baseURL == "" || pattern == "" {
		return ""
	}
	var sb strings.Builder
	sb.WriteString(baseURL)
	for i := 1; i <= count; i++ {
		if i > 1 {
			sb.WriteString(" ")
		}
		sb.WriteString(fmt.Sprintf(pattern, i))
	}
	return sb.String()
}

func templateURLs(baseURL, pattern string, count int) []string {
	urls := make([]string, 0, count)
	for i := 1; i <= count; i++ {
		urls = append(urls, baseURL+fmt.Sprintf(pattern, i))
	}
	return urls
}

// ---------- mapping ----------

func mapManga(m rawManga) (*store.Manga, []store.Tag, error) {
	title := strings.TrimSpace(m.Title.Rendered)
	slug := m.Slug
	if slug == "" {
		slug = slugify(title)
	}

	desc := stripTags(m.Content.Rendered)
	summary := stripTags(m.Excerpt.Rendered)
	if summary == "" && desc != "" {
		if len(desc) > 300 {
			summary = desc[:300] + "..."
		} else {
			summary = desc
		}
	}

	sourceURL := m.Link
	coverURL := ""
	thumbURL := ""
	// featured_media is an ID only in merged.json; thumbnail comes from meta
	if v, ok := m.Meta.Meta["thumbnail"]; ok {
		if s, ok := v.(string); ok && s != "" {
			thumbURL = s
			coverURL = s
		}
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

	for _, t := range m.Meta.Tax {
		addTag(t.Name, t.Slug, t.Taxonomy)
	}

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

func str(v interface{}) string {
	switch s := v.(type) {
	case string:
		return s
	case []byte:
		return string(s)
	default:
		return fmt.Sprintf("%v", v)
	}
}

func parseIntPtr(v interface{}) (int, bool) {
	if v == nil {
		return 0, false
	}
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

func main() {
	if len(os.Args) < 3 {
		log.Fatalf("usage: import_merged <db_path> <merged.json>")
	}
	dbPath := os.Args[1]
	jsonPath := os.Args[2]

	db, err := sqlite.Open(dbPath)
	if err != nil {
		log.Fatalf("open database: %v", err)
	}
	defer db.Close()

	if err := sqlite.Migrate(db); err != nil {
		log.Fatalf("migrate database: %v", err)
	}

	repo := store.New(db)

	f, err := os.Open(jsonPath)
	if err != nil {
		log.Fatalf("open json: %v", err)
	}
	defer f.Close()

	dec := json.NewDecoder(f)

	// Read opening [
	if _, err := dec.Token(); err != nil {
		log.Fatalf("read array start: %v", err)
	}

	mangaCount := 0
	chapterCount := 0
	pageCount := 0
	tagCount := 0

	for dec.More() {
		var raw json.RawMessage
		if err := dec.Decode(&raw); err != nil {
			log.Fatalf("decode element: %v", err)
		}

		// Try to unmarshal as manga (has "id" field at top level)
		var m rawManga
		if err := json.Unmarshal(raw, &m); err != nil {
			log.Printf("skip element: %v", err)
			continue
		}

		if m.ID == 0 && m.Slug == "" {
			log.Printf("skip element without id or slug")
			continue
		}

		// Map manga
		mm, tags, err := mapManga(m)
		if err != nil {
			log.Printf("map manga %q: %v", m.Slug, err)
			continue
		}

		if err := repo.UpsertManga(mm); err != nil {
			log.Printf("upsert manga %q: %v", m.Slug, err)
			continue
		}
		mangaCount++

		// Import tags
		for _, tag := range tags {
			t, err := repo.GetOrCreateTag(tag.Name, tag.Slug, tag.Category)
			if err != nil {
				log.Printf("get/create tag %q: %v", tag.Name, err)
				continue
			}
			if err := repo.LinkMangaTag(mm.ID, t.ID); err != nil {
				log.Printf("link manga tag %q: %v", tag.Name, err)
				continue
			}
			tagCount++
		}

		// Import embedded chapters
		for _, c := range m.Chapters {
			chapter := &store.Chapter{
				MangaID:      mm.ID,
				SourceIndex:  c.Index,
				Number:       chapterNumber(c.Title, c.Index),
				Title:        strings.TrimSpace(c.Title),
				SourceURL:    c.URL,
				PageCount:    c.PageCount,
				PagesTemplate: buildTemplate(c.Pages.BaseURL, c.Pages.Pattern, c.PageCount),
			}
			if t, err := parseTime(c.Date); err == nil {
				chapter.PublishedAt = t
			} else {
				chapter.PublishedAt = time.Now().UTC()
			}
			if err := repo.UpsertChapter(chapter); err != nil {
				log.Printf("upsert chapter index %d for manga %q: %v", c.Index, m.Slug, err)
				continue
			}

			if err := repo.DeleteChapterPages(chapter.ID); err != nil {
				log.Printf("delete pages for chapter %q: %v", chapter.ID, err)
				continue
			}

			pc := 0
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
				if err := repo.InsertPage(&store.Page{
					ChapterID: chapter.ID,
					Idx:       i,
					URL:       u,
				}); err != nil {
					log.Printf("insert page %d for chapter %q: %v", i, chapter.ID, err)
					continue
				}
				pc++
			}
			if pc > 0 {
				if err := repo.UpdateChapterPageCount(chapter.ID, pc); err != nil {
					log.Printf("update page count for chapter %q: %v", chapter.ID, err)
				}
			}
			chapterCount++
			pageCount += pc
		}

		if mangaCount%50 == 0 {
			log.Printf("progress: manga=%d chapters=%d pages=%d tags=%d",
				mangaCount, chapterCount, pageCount, tagCount)
		}
	}

	// Read closing ]
	if _, err := dec.Token(); err != nil {
		log.Fatalf("read array end: %v", err)
	}

	log.Printf("import complete: manga=%d chapters=%d pages=%d tags=%d",
		mangaCount, chapterCount, pageCount, tagCount)
}
