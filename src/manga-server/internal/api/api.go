package api

import (
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"strconv"
	"strings"

	"mugiko/manga-server/internal/store"
)

// ---------- DTOs ----------

type ErrorResponse struct {
	Error   string `json:"error"`
	Message string `json:"message,omitempty"`
}

type ProviderInfo struct {
	Name        string `json:"name"`
	Description string `json:"description"`
	APIVersion  string `json:"api_version"`
}

type TagResponse struct {
	ID       string `json:"id"`
	Name     string `json:"name"`
	Slug     string `json:"slug"`
	Category string `json:"category"`
}

type TagListResponse struct {
	Items      []TagResponse `json:"items"`
	Page       int           `json:"page"`
	PageSize   int           `json:"page_size"`
	Total      int           `json:"total"`
	TotalPages int           `json:"total_pages"`
}

type ChapterSummary struct {
	ID         string `json:"id"`
	MangaID    string `json:"manga_id"`
	Number     string `json:"number"`
	Title      string `json:"title"`
	PublishedAt string `json:"published_at"`
	PageCount  int    `json:"page_count"`
}

type MangaSummary struct {
	ID              string            `json:"id"`
	Slug            string            `json:"slug"`
	Title           string            `json:"title"`
	AlternativeTitles []string        `json:"alternative_titles"`
	CoverURL        string            `json:"cover_url"`
	ThumbnailURL    string            `json:"thumbnail_url"`
	Tags            []TagResponse     `json:"tags"`
	Score           float64           `json:"score"`
	Views           int               `json:"views"`
	LatestChapters  []ChapterSummary  `json:"latest_chapters"`
	UpdatedAt       string            `json:"updated_at"`
}

type MangaDetail struct {
	MangaSummary
	Description string `json:"description"`
	SourceURL   string `json:"source_url"`
	CreatedAt   string `json:"created_at"`
}

type MangaListResponse struct {
	Items      []MangaSummary `json:"items"`
	Page       int            `json:"page"`
	PageSize   int            `json:"page_size"`
	Total      int            `json:"total"`
	TotalPages int            `json:"total_pages"`
}

type ChapterDetail struct {
	ID          string         `json:"id"`
	MangaID     string         `json:"manga_id"`
	Number      string         `json:"number"`
	Title       string         `json:"title"`
	PublishedAt string         `json:"published_at"`
	PageCount   int            `json:"page_count"`
	Pages       []PageResponse `json:"pages"`
}

type PageResponse struct {
	Index  int    `json:"index"`
	URL    string `json:"url"`
	Width  int    `json:"width"`
	Height int    `json:"height"`
}

type PageListResponse struct {
	ChapterID  string         `json:"chapter_id"`
	Width      int            `json:"width"`
	Height     int            `json:"height"`
	Pages      []PageResponse `json:"pages"`
	Page       int            `json:"page"`
	PageSize   int            `json:"page_size"`
	Total      int            `json:"total"`
	TotalPages int            `json:"total_pages"`
}

// ---------- server ----------

type Server struct {
	store *store.Repository
}

func New(s *store.Repository) *Server {
	return &Server{store: s}
}

func (s *Server) Routes() *http.ServeMux {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /health", s.health)

	// Built-in provider API
	mux.HandleFunc("GET /api/v1/builtin-provider/info", s.providerInfo)
	mux.HandleFunc("GET /api/v1/builtin-provider/tags", s.listTags)
	mux.HandleFunc("GET /api/v1/builtin-provider/filters", s.listFilters)
	mux.HandleFunc("GET /api/v1/builtin-provider/manga", s.listManga)
	mux.HandleFunc("GET /api/v1/builtin-provider/manga/{id}", s.getManga)
	mux.HandleFunc("GET /api/v1/builtin-provider/manga/{id}/chapters", s.listMangaChapters)
	mux.HandleFunc("GET /api/v1/builtin-provider/chapters", s.listChapters)
	mux.HandleFunc("GET /api/v1/builtin-provider/chapters/{id}", s.getChapter)
	mux.HandleFunc("GET /api/v1/builtin-provider/chapters/{id}/pages", s.listChapterPages)

	return mux
}

func (s *Server) cors(w http.ResponseWriter, r *http.Request) {
	allowCORS(w)
	w.WriteHeader(http.StatusNoContent)
}

func allowCORS(w http.ResponseWriter) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
}

func (s *Server) writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func (s *Server) writeError(w http.ResponseWriter, status int, errCode, message string) {
	allowCORS(w)
	s.writeJSON(w, status, ErrorResponse{Error: errCode, Message: message})
}

// ---------- handlers ----------

func (s *Server) health(w http.ResponseWriter, r *http.Request) {
	allowCORS(w)
	s.writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *Server) providerInfo(w http.ResponseWriter, r *http.Request) {
	allowCORS(w)
	s.writeJSON(w, http.StatusOK, ProviderInfo{
		Name:        "Mugiko Manga Server",
		Description: "Standalone manga server backed by SQLite",
		APIVersion:  "1",
	})
}

// resolveManga looks up a manga by ID or slug. Returns false (and writes an
// error response) when not found.
func (s *Server) resolveManga(w http.ResponseWriter, id string) (*store.Manga, bool) {
	m, err := s.store.GetManga(id)
	if err != nil {
		if !errors.Is(err, sql.ErrNoRows) {
			s.writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", err.Error())
			return nil, false
		}
		m2, err2 := s.store.GetMangaBySlug(id)
		if err2 != nil {
			if !errors.Is(err2, sql.ErrNoRows) {
				s.writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", err2.Error())
				return nil, false
			}
			s.writeError(w, http.StatusNotFound, "MANGA_NOT_FOUND", "manga not found")
			return nil, false
		}
		m = m2
	}
	if m == nil {
		s.writeError(w, http.StatusNotFound, "MANGA_NOT_FOUND", "manga not found")
		return nil, false
	}
	return m, true
}

func (s *Server) listTags(w http.ResponseWriter, r *http.Request) {
	allowCORS(w)
	q := r.URL.Query()
	f := store.TagFilter{
		Category: q.Get("category"),
		Q:        q.Get("q"),
		Order:    q.Get("order"),
		Page:     parseIntParam(q.Get("page"), 1),
		PageSize: parseIntParam(q.Get("page_size"), 50),
	}
	if f.PageSize > 200 {
		f.PageSize = 200
	}
	items, total, err := s.store.ListTags(f)
	if err != nil {
		s.writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", err.Error())
		return
	}
	out := make([]TagResponse, 0, len(items))
	for _, t := range items {
		out = append(out, TagResponse{ID: t.ID, Name: t.Name, Slug: t.Slug, Category: t.Category})
	}
	totalPages := totalPages(total, f.PageSize)
	s.writeJSON(w, http.StatusOK, TagListResponse{
		Items:      out,
		Page:       f.Page,
		PageSize:   f.PageSize,
		Total:      total,
		TotalPages: totalPages,
	})
}

type FilterListResponse struct {
	Items map[string][]TagResponse `json:"items"`
}

func (s *Server) listFilters(w http.ResponseWriter, r *http.Request) {
	allowCORS(w)
	// Fetch all tags (no pagination) so every filter category is represented.
	items, _, err := s.store.ListTags(store.TagFilter{PageSize: 10000})
	if err != nil {
		s.writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", err.Error())
		return
	}
	grouped := make(map[string][]TagResponse)
	for _, t := range items {
		grouped[t.Category] = append(grouped[t.Category], TagResponse{
			ID:       t.ID,
			Name:     t.Name,
			Slug:     t.Slug,
			Category: t.Category,
		})
	}
	s.writeJSON(w, http.StatusOK, FilterListResponse{Items: grouped})
}

func (s *Server) listManga(w http.ResponseWriter, r *http.Request) {
	allowCORS(w)
	q := r.URL.Query()
	f := store.MangaFilter{
		Q:           q.Get("q"),
		Tags:        strings.FieldsFunc(q.Get("tags"), func(c rune) bool { return c == ',' }),
		Genre:       q.Get("genre"),
		Author:      q.Get("author"),
		Artist:      q.Get("artist"),
		Status:      q.Get("status"),
		Type:        q.Get("type"),
		Sort:        q.Get("sort"),
		Order:       q.Get("order"),
		Page:        parseIntParam(q.Get("page"), 1),
		PageSize:    parseIntParam(q.Get("page_size"), 20),
	}
	if f.PageSize > 100 {
		f.PageSize = 100
	}
	if v := q.Get("year"); v != "" {
		if y, err := strconv.Atoi(v); err == nil {
			f.Year = &y
		}
	}
	if v := q.Get("min_score"); v != "" {
		if sc, err := strconv.ParseFloat(v, 64); err == nil {
			f.MinScore = &sc
		}
	}

	items, total, err := s.store.ListManga(f)
	if err != nil {
		s.writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", err.Error())
		return
	}

	out := make([]MangaSummary, 0, len(items))
	for _, m := range items {
		out = append(out, s.mangaSummary(m, true))
	}
	totalPages := totalPages(total, f.PageSize)
	s.writeJSON(w, http.StatusOK, MangaListResponse{
		Items:      out,
		Page:       f.Page,
		PageSize:   f.PageSize,
		Total:      total,
		TotalPages: totalPages,
	})
}

func (s *Server) getManga(w http.ResponseWriter, r *http.Request) {
	allowCORS(w)
	id := r.PathValue("id")
	if id == "" {
		s.writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "manga id is required")
		return
	}
	m, ok := s.resolveManga(w, id)
	if !ok {
		return
	}
	s.writeJSON(w, http.StatusOK, s.mangaDetail(m))
}

func (s *Server) listMangaChapters(w http.ResponseWriter, r *http.Request) {
	allowCORS(w)
	id := r.PathValue("id")
	if id == "" {
		s.writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "manga id is required")
		return
	}
	m, ok := s.resolveManga(w, id)
	if !ok {
		return
	}

	q := r.URL.Query()
	f := store.ChapterFilter{
		Sort:    q.Get("sort"),
		Order:   q.Get("order"),
		Page:    parseIntParam(q.Get("page"), 1),
		PageSize: parseIntParam(q.Get("page_size"), 50),
	}
	if f.PageSize > 200 {
		f.PageSize = 200
	}

	items, total, err := s.store.ListChapters(m.ID, f)
	if err != nil {
		s.writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", err.Error())
		return
	}
	out := make([]ChapterSummary, 0, len(items))
	for _, c := range items {
		out = append(out, chapterSummary(c))
	}
	totalPages := totalPages(total, f.PageSize)
	s.writeJSON(w, http.StatusOK, ChapterListResponse{
		Items:      out,
		Page:       f.Page,
		PageSize:   f.PageSize,
		Total:      total,
		TotalPages: totalPages,
	})
}

type ChapterListResponse struct {
	Items      []ChapterSummary `json:"items"`
	Page       int              `json:"page"`
	PageSize   int              `json:"page_size"`
	Total      int              `json:"total"`
	TotalPages int              `json:"total_pages"`
}

func (s *Server) listChapters(w http.ResponseWriter, r *http.Request) {
	allowCORS(w)
	q := r.URL.Query()
	mangaID := q.Get("manga_id")
	if mangaID == "" {
		s.writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "manga_id is required")
		return
	}
	m, ok := s.resolveManga(w, mangaID)
	if !ok {
		return
	}

	f := store.ChapterFilter{
		Sort:    q.Get("sort"),
		Order:   q.Get("order"),
		Page:    parseIntParam(q.Get("page"), 1),
		PageSize: parseIntParam(q.Get("page_size"), 50),
	}
	if f.PageSize > 200 {
		f.PageSize = 200
	}

	items, total, err := s.store.ListChapters(m.ID, f)
	if err != nil {
		s.writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", err.Error())
		return
	}
	out := make([]ChapterSummary, 0, len(items))
	for _, c := range items {
		out = append(out, chapterSummary(c))
	}
	totalPages := totalPages(total, f.PageSize)
	s.writeJSON(w, http.StatusOK, ChapterListResponse{
		Items:      out,
		Page:       f.Page,
		PageSize:   f.PageSize,
		Total:      total,
		TotalPages: totalPages,
	})
}

func (s *Server) getChapter(w http.ResponseWriter, r *http.Request) {
	allowCORS(w)
	id := r.PathValue("id")
	if id == "" {
		s.writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "chapter id is required")
		return
	}
	c, err := s.store.GetChapter(id)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			s.writeError(w, http.StatusNotFound, "CHAPTER_NOT_FOUND", "chapter not found")
			return
		}
		s.writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", err.Error())
		return
	}
	if c == nil {
		s.writeError(w, http.StatusNotFound, "CHAPTER_NOT_FOUND", "chapter not found")
		return
	}
	pages, err := s.store.ListChapterPages(c.ID)
	if err != nil {
		s.writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", err.Error())
		return
	}
	pageResps := make([]PageResponse, 0, len(pages))
	width, height := 0, 0
	for _, p := range pages {
		pageResps = append(pageResps, PageResponse{Index: p.Idx, URL: p.URL, Width: p.Width, Height: p.Height})
		if p.Width > width {
			width = p.Width
		}
		if p.Height > height {
			height = p.Height
		}
	}
	s.writeJSON(w, http.StatusOK, ChapterDetail{
		ID:          c.ID,
		MangaID:     c.MangaID,
		Number:      c.Number,
		Title:       c.Title,
		PublishedAt: c.PublishedAt.Format("2006-01-02T15:04:05Z"),
		PageCount:   c.PageCount,
		Pages:       pageResps,
	})
}

func (s *Server) listChapterPages(w http.ResponseWriter, r *http.Request) {
	allowCORS(w)
	id := r.PathValue("id")
	if id == "" {
		s.writeError(w, http.StatusBadRequest, "INVALID_REQUEST", "chapter id is required")
		return
	}
	c, err := s.store.GetChapter(id)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			s.writeError(w, http.StatusNotFound, "CHAPTER_NOT_FOUND", "chapter not found")
			return
		}
		s.writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", err.Error())
		return
	}
	if c == nil {
		s.writeError(w, http.StatusNotFound, "CHAPTER_NOT_FOUND", "chapter not found")
		return
	}

	q := r.URL.Query()
	page := parseIntParam(q.Get("page"), 1)
	pageSize := parseIntParam(q.Get("page_size"), 50)
	if pageSize > 200 {
		pageSize = 200
	}

	pages, err := s.store.ListChapterPages(c.ID)
	if err != nil {
		s.writeError(w, http.StatusInternalServerError, "INTERNAL_ERROR", err.Error())
		return
	}
	total := len(pages)
	start := (page - 1) * pageSize
	if start > total {
		start = total
	}
	end := start + pageSize
	if end > total {
		end = total
	}
	slice := pages[start:end]

	pageResps := make([]PageResponse, 0, len(slice))
	width, height := 0, 0
	for _, p := range slice {
		pageResps = append(pageResps, PageResponse{Index: p.Idx, URL: p.URL, Width: p.Width, Height: p.Height})
		if p.Width > width {
			width = p.Width
		}
		if p.Height > height {
			height = p.Height
		}
	}
	s.writeJSON(w, http.StatusOK, PageListResponse{
		ChapterID:  c.ID,
		Width:      width,
		Height:     height,
		Pages:      pageResps,
		Page:       page,
		PageSize:   pageSize,
		Total:      total,
		TotalPages: totalPages(total, pageSize),
	})
}

// ---------- conversions ----------

func (s *Server) mangaSummary(m *store.Manga, withChapters bool) MangaSummary {
	tags, _ := s.store.GetMangaTags(m.ID)
	tagResps := make([]TagResponse, 0, len(tags))
	for _, t := range tags {
		tagResps = append(tagResps, TagResponse{ID: t.ID, Name: t.Name, Slug: t.Slug, Category: t.Category})
	}
	alt := m.AltTitles
	if alt == nil {
		alt = []string{}
	}
	var latest []ChapterSummary
	if withChapters {
		chaps, _, err := s.store.ListChapters(m.ID, store.ChapterFilter{Sort: "published_at", Order: "desc", Page: 1, PageSize: 3})
		if err == nil {
			latest = make([]ChapterSummary, 0, len(chaps))
			for _, c := range chaps {
				latest = append(latest, chapterSummary(c))
			}
		}
		if latest == nil {
			latest = []ChapterSummary{}
		}
	}
	return MangaSummary{
		ID:               m.ID,
		Slug:             m.Slug,
		Title:            m.Title,
		AlternativeTitles: alt,
		CoverURL:         m.CoverURL,
		ThumbnailURL:     m.ThumbnailURL,
		Tags:             tagResps,
		Score:            m.Score,
		Views:            m.Views,
		LatestChapters:   latest,
		UpdatedAt:        m.UpdatedAt.Format("2006-01-02T15:04:05Z"),
	}
}

func (s *Server) mangaDetail(m *store.Manga) MangaDetail {
	summary := s.mangaSummary(m, true)
	return MangaDetail{
		MangaSummary: summary,
		Description:  m.Description,
		SourceURL:    m.SourceURL,
		CreatedAt:    m.CreatedAt.Format("2006-01-02T15:04:05Z"),
	}
}

func chapterSummary(c *store.Chapter) ChapterSummary {
	return ChapterSummary{
		ID:          c.ID,
		MangaID:     c.MangaID,
		Number:      c.Number,
		Title:       c.Title,
		PublishedAt: c.PublishedAt.Format("2006-01-02T15:04:05Z"),
		PageCount:   c.PageCount,
	}
}

// ---------- helpers ----------

func parseIntParam(v string, def int) int {
	if v == "" {
		return def
	}
	n, err := strconv.Atoi(v)
	if err != nil || n < 1 {
		return def
	}
	return n
}

func totalPages(total, pageSize int) int {
	if pageSize <= 0 {
		return 0
	}
	return (total + pageSize - 1) / pageSize
}
