package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"mugiko/llm-worker/internal/worker"
)

func main() {
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	cfg, err := worker.LoadConfig()
	if err != nil {
		log.Fatalf("llm worker config failed: %v", err)
	}
	w, err := worker.New(cfg)
	if err != nil {
		log.Fatalf("llm worker init failed: %v", err)
	}
	if err := w.Run(ctx); err != nil {
		log.Fatalf("llm worker failed: %v", err)
	}
}