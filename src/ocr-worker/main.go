package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"mugiko/ocr-worker/internal/worker"
)

func main() {
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	cfg, err := worker.LoadConfig()
	if err != nil {
		log.Fatalf("ocr worker config failed: %v", err)
	}
	w, err := worker.New(cfg)
	if err != nil {
		log.Fatalf("ocr worker init failed: %v", err)
	}
	if err := w.Run(ctx); err != nil {
		log.Fatalf("ocr worker failed: %v", err)
	}
}
