package importer

import (
	"strings"
	"testing"
)

func TestMapMangaFields(t *testing.T) {
	m := wpManga{
		Slug: "test-slug",
		Title: struct {
			Rendered string `json:"rendered"`
		}{Rendered: "Test Manga"},
		Content: struct {
			Rendered string `json:"rendered"`
		}{Rendered: "<p>Hello world</p>"},
		Excerpt: struct {
			Rendered string `json:"rendered"`
		}{Rendered: "<p>Excerpt</p>"},
		Link: "https://example.com/manga/test-slug/",
		Meta: struct {
			Meta map[string]interface{} `json:"meta"`
			Tax  []wpTax                `json:"tax"`
		}{
			Meta: map[string]interface{}{
				"score":           "7.2",
				"views":           "12345",
				"released":        "2021",
				"serialization":   "Weekly Shonen Jump",
				"alternative_title": "Alt One, Alt Two",
				"thumbnail":       "https://example.com/thumb.jpg",
			},
			Tax: []wpTax{
				{TermID: 1, Name: "Action", Slug: "action", Taxonomy: "genre"},
				{TermID: 2, Name: "Author Name", Slug: "author-name", Taxonomy: "series-author"},
			},
		},
		Embedded: struct {
			FeaturedMedia []wpMedia `json:"wp:featuredmedia"`
			Terms         [][]wpTerm `json:"wp:term"`
		}{
			FeaturedMedia: []wpMedia{{SourceURL: "https://example.com/cover.jpg"}},
		},
	}

	mm, tags, err := mapManga(m)
	if err != nil {
		t.Fatalf("mapManga: %v", err)
	}
	if mm.Title != "Test Manga" {
		t.Fatalf("title: %s", mm.Title)
	}
	if mm.Slug != "test-slug" {
		t.Fatalf("slug: %s", mm.Slug)
	}
	if mm.Description != "Hello world" {
		t.Fatalf("description: %s", mm.Description)
	}
	if mm.Summary != "Excerpt" {
		t.Fatalf("summary: %s", mm.Summary)
	}
	if mm.Score != 7.2 {
		t.Fatalf("score: %f", mm.Score)
	}
	if mm.Views != 12345 {
		t.Fatalf("views: %d", mm.Views)
	}
	if mm.ReleaseYear == nil || *mm.ReleaseYear != 2021 {
		t.Fatalf("release year: %v", mm.ReleaseYear)
	}
	if mm.Serialization != "Weekly Shonen Jump" {
		t.Fatalf("serialization: %s", mm.Serialization)
	}
	if len(mm.AltTitles) != 2 || mm.AltTitles[0] != "Alt One" || mm.AltTitles[1] != "Alt Two" {
		t.Fatalf("alt titles: %v", mm.AltTitles)
	}
	if mm.CoverURL != "https://example.com/cover.jpg" {
		t.Fatalf("cover: %s", mm.CoverURL)
	}
	if mm.ThumbnailURL != "https://example.com/cover.jpg" {
		t.Fatalf("thumbnail: %s", mm.ThumbnailURL)
	}
	if !strings.Contains(mm.SearchText, "test manga") {
		t.Fatalf("search text missing title: %s", mm.SearchText)
	}
	if !strings.Contains(mm.SearchText, "action") {
		t.Fatalf("search text missing tag: %s", mm.SearchText)
	}
	if len(tags) != 2 {
		t.Fatalf("expected 2 tags, got %d", len(tags))
	}
	if tags[0].Category != "genre" || tags[0].Name != "Action" {
		t.Fatalf("tag0: %+v", tags[0])
	}
	if tags[1].Category != "series-author" || tags[1].Name != "Author Name" {
		t.Fatalf("tag1: %+v", tags[1])
	}
}

func TestChapterNumberParsing(t *testing.T) {
	cases := []struct {
		title string
		index int
		want  string
	}{
		{"Chapter 1", 0, "1"},
		{"Chapter 10.5", 0, "10.5"},
		{"Chapter 20.3", 7, "20.3"},
		{"Volume 5", 3, "3"},
		{"", 9, "9"},
	}
	for _, c := range cases {
		if got := chapterNumber(c.title, c.index); got != c.want {
			t.Fatalf("chapterNumber(%q, %d) = %q, want %q", c.title, c.index, got, c.want)
		}
	}
}

func TestTemplateURLs(t *testing.T) {
	got := templateURLs("https://rcdn.kyut.dev/1/manga/chapter-1/", "{:01d}.jpg", 3)
	want := []string{
		"https://rcdn.kyut.dev/1/manga/chapter-1/1.jpg",
		"https://rcdn.kyut.dev/1/manga/chapter-1/2.jpg",
		"https://rcdn.kyut.dev/1/manga/chapter-1/3.jpg",
	}
	for i := range got {
		if got[i] != want[i] {
			t.Fatalf("templateURLs[%d] = %q, want %q", i, got[i], want[i])
		}
	}
}
