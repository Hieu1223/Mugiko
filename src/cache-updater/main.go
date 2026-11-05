package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"mugiko/cache-updater/internal/updater"
)

func main() {
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	u, err := updater.NewFromEnv()
	if err != nil {
		log.Fatalf("cache updater init failed: %v", err)
	}
	if err := u.Run(ctx); err != nil {
		log.Fatalf("cache updater failed: %v", err)
	}
}