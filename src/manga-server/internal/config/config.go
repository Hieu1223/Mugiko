package config

import (
	"flag"
	"os"
)

type Config struct {
	Addr        string
	DBPath      string
	MangaFile   string
	ChapterFile string
	ImportOnly  bool
	ServeOnly   bool
}

func Load() *Config {
	cfg := &Config{}
	fs := flag.NewFlagSet("manga-server", flag.ContinueOnError)
	fs.StringVar(&cfg.Addr, "addr", getEnv("MANGA_ADDR", ":8090"), "listen address")
	fs.StringVar(&cfg.DBPath, "db", getEnv("MANGA_DB_PATH", "manga.db"), "sqlite database path")
	fs.StringVar(&cfg.MangaFile, "manga", getEnv("MANGA_MANGA_FILE", ""), "manga JSON file or directory to import")
	fs.StringVar(&cfg.ChapterFile, "chapters", getEnv("MANGA_CHAPTER_FILE", ""), "chapter JSON file or directory to import")
	fs.BoolVar(&cfg.ImportOnly, "import-only", false, "import data then exit")
	fs.BoolVar(&cfg.ServeOnly, "serve-only", false, "serve without importing")
	_ = fs.Parse(os.Args[1:])
	return cfg
}

func getEnv(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}
