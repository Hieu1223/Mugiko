package persistent

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
)

// StreamMessage is a single entry read from a Redis stream.
type StreamMessage struct {
	ID     string
	Values map[string]any
}

var (
	redisClient *redis.Client
	redisOnce   sync.Once
	redisErr    error
)

// GetRedisClient returns the shared Redis client (initializing it from REDIS_URL).
func GetRedisClient() (*redis.Client, error) {
	return getRedisClient()
}

func getRedisClient() (*redis.Client, error) {
	redisOnce.Do(func() {
		redisURL := os.Getenv("REDIS_URL")
		if redisURL == "" {
			redisErr = errors.New("Env must contain REDIS_URL")
			return
		}

		opts, err := redis.ParseURL(redisURL)
		if err != nil {
			redisErr = fmt.Errorf("invalid REDIS_URL: %w", err)
			return
		}

		redisClient = redis.NewClient(opts)
	})
	return redisClient, redisErr
}

// ListenRedisStream reads new entries from the Redis stream named key and
// sends them to ch. It blocks until ctx is cancelled or a non-recoverable
// error occurs. Only entries added after the listener starts are delivered.
//
// The caller owns ch and is responsible for closing it.
func ListenRedisStream(ctx context.Context, key string, ch chan<- StreamMessage) error {
	client, err := getRedisClient()
	if err != nil {
		return err
	}

	lastID := "$"
	for {
		streams, err := client.XRead(ctx, &redis.XReadArgs{
			Streams: []string{key, lastID},
			Count:   10,
			Block:   5 * time.Second,
		}).Result()
		if err != nil {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			if errors.Is(err, redis.Nil) {
				continue
			}

			log.Printf("Redis stream %q read failed: %v", key, err)
			select {
			case <-time.After(time.Second):
			case <-ctx.Done():
				return ctx.Err()
			}
			continue
		}

		for _, stream := range streams {
			for _, message := range stream.Messages {
				select {
				case ch <- StreamMessage{ID: message.ID, Values: message.Values}:
					lastID = message.ID
				case <-ctx.Done():
					return ctx.Err()
				}
			}
		}
	}
}
