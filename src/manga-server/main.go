package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"mugiko/manga-server/internal/api"
	"mugiko/manga-server/internal/config"
	"mugiko/manga-server/internal/importer"
	"mugiko/manga-server/internal/sqlite"
	"mugiko/manga-server/internal/store"
)

func main() {
	args := os.Args[1:]
	cmd := "serve"
	if len(args) > 0 && args[0] != "" && args[0][0] != '-' {
		cmd = args[0]
		args = args[1:]
	}

	cfg := config.Load()
	// Re-parse flags for the remaining args so subcommand-specific flags work.
	fs := flag.NewFlagSet(cmd, flag.ContinueOnError)
	fs.StringVar(&cfg.Addr, "addr", cfg.Addr, "listen address")
	fs.StringVar(&cfg.DBPath, "db", cfg.DBPath, "sqlite database path")
	fs.StringVar(&cfg.MangaFile, "manga", cfg.MangaFile, "manga JSON file or directory to import")
	fs.StringVar(&cfg.ChapterFile, "chapters", cfg.ChapterFile, "chapter JSON file or directory to import")
	fs.BoolVar(&cfg.ImportOnly, "import-only", cfg.ImportOnly, "import data then exit")
	fs.BoolVar(&cfg.ServeOnly, "serve-only", cfg.ServeOnly, "serve without importing")
	_ = fs.Parse(args)

	db, err := sqlite.Open(cfg.DBPath)
	if err != nil {
		log.Fatalf("open database: %v", err)
	}
	defer db.Close()

	if err := sqlite.Migrate(db); err != nil {
		log.Fatalf("migrate database: %v", err)
	}

	repo := store.New(db)
	srv := api.New(repo)

	switch cmd {
	case "import":
		cfg.ImportOnly = true
		fallthrough
	case "serve":
		if !cfg.ServeOnly {
			if cfg.MangaFile != "" || cfg.ChapterFile != "" {
				res, err := importer.Import(repo, cfg.MangaFile, cfg.ChapterFile)
				if err != nil {
					log.Fatalf("import: %v", err)
				}
				log.Printf("import complete: manga=%d tags=%d chapters=%d pages=%d",
					res.Manga, res.Tags, res.Chapters, res.Pages)
			}
		}
		if cmd == "import" || cfg.ImportOnly {
			log.Println("import-only: exiting")
			return
		}
	default:
		log.Fatalf("unknown command %q (use 'import' or 'serve')", cmd)
	}

	server := &http.Server{
		Addr:         cfg.Addr,
		Handler:      srv.Routes(),
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	go func() {
		log.Printf("manga-server listening on %s", cfg.Addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("shutting down...")
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		log.Fatalf("shutdown: %v", err)
	}
}
