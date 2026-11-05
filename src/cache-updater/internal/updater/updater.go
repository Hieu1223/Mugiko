package updater

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
)

const progressTTL = 24 * time.Hour

type Updater struct {
	redis    *redis.Client
	streams  []string
	group    string
	consumer string
}

func NewFromEnv() (*Updater, error) {
	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		return nil, fmt.Errorf("REDIS_URL is required")
	}
	opts, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, fmt.Errorf("invalid REDIS_URL: %w", err)
	}
	client := redis.NewClient(opts)

	streams := []string{"chat_progress", "llm_progress", "subtitle_progress"}
	if v := os.Getenv("PROGRESS_STREAMS"); v != "" {
		streams = strings.Split(v, ",")
	}
	group := os.Getenv("CONSUMER_GROUP")
	if group == "" {
		group = "cache-updater"
	}
	consumer := os.Getenv("CONSUMER_NAME")
	if consumer == "" {
		consumer = "cache-updater-1"
	}
	return &Updater{redis: client, streams: streams, group: group, consumer: consumer}, nil
}

func groupMissing(err error) bool {
	return err != nil && strings.Contains(err.Error(), "NOGROUP")
}

func (u *Updater) ensureGroup(ctx context.Context, stream string) error {
	// XGROUP CREATE stream group 0 MKSTREAM — creates the stream if missing,
	// then creates the consumer group at the beginning.
	_, err := u.redis.Do(ctx, "XGROUP", "CREATE", stream, u.group, "0", "MKSTREAM").Result()
	if err != nil {
		if strings.Contains(err.Error(), "BUSYGROUP") {
			return nil
		}
		return err
	}
	return nil
}

func (u *Updater) Run(ctx context.Context) error {
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		// Ensure consumer groups exist on every stream before reading.
		for _, s := range u.streams {
			if err := u.ensureGroup(ctx, s); err != nil {
				log.Printf("cache updater: create group %s on %s: %v", u.group, s, err)
			}
		}

		streamArgs := []string{}
		for _, s := range u.streams {
			streamArgs = append(streamArgs, s, ">")
		}
		res, err := u.redis.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group:    u.group,
			Consumer: u.consumer,
			Streams:  streamArgs,
			Count:    10,
			Block:    5 * time.Second,
		}).Result()
		if err != nil {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			if err == redis.Nil {
				time.Sleep(100 * time.Millisecond)
				continue
			}
			if groupMissing(err) {
				log.Printf("cache updater: group missing, retrying: %v", err)
				time.Sleep(1 * time.Second)
				continue
			}
			log.Printf("cache updater read failed: %v", err)
			time.Sleep(time.Second)
			continue
		}
		for _, stream := range res {
			for _, msg := range stream.Messages {
				if err := u.handle(ctx, stream.Stream, msg); err != nil {
					log.Printf("cache updater handle failed: %v", err)
					continue
				}
				if err := u.redis.XAck(ctx, stream.Stream, u.group, msg.ID).Err(); err != nil {
					log.Printf("cache updater ack failed: %v", err)
				}
			}
		}
	}
}

func (u *Updater) handle(ctx context.Context, stream string, msg redis.XMessage) error {
	entityType := toString(msg.Values["entity_type"])
	entityID := toString(msg.Values["entity_id"])
	if entityType == "" {
		entityType = streamPrefix(stream)
	}
	if entityID == "" {
		entityID = toString(msg.Values["id"])
	}
	if entityID == "" {
		return fmt.Errorf("missing entity_id in %s", stream)
	}
	prefix := progressPrefix(entityType)
	key := prefix + ":" + entityID

	snapshot := map[string]any{}
	for k, v := range msg.Values {
		snapshot[k] = v
	}
	b, err := json.Marshal(snapshot)
	if err != nil {
		return err
	}

	ttl := progressTTL
	if v := os.Getenv("PROGRESS_TTL_SECONDS"); v != "" {
		var secs int
		fmt.Sscanf(v, "%d", &secs)
		if secs > 0 {
			ttl = time.Duration(secs) * time.Second
		}
	}

	pipe := u.redis.TxPipeline()
	pipe.Set(ctx, key, string(b), ttl)
	pipe.Publish(ctx, key, string(b))
	_, err = pipe.Exec(ctx)
	return err
}

func streamPrefix(stream string) string {
	switch stream {
	case "chat_progress":
		return "chat"
	case "llm_progress":
		return "llm"
	case "subtitle_progress":
		return "subtitle"
	}
	return strings.TrimSuffix(stream, "_progress")
}

func progressPrefix(entityType string) string {
	switch entityType {
	case "chat", "conversation":
		return "chat:progress"
	case "llm", "llm_job":
		return "llm:progress"
	case "subtitle":
		return "subtitle:progress"
	}
	if strings.HasSuffix(entityType, ":progress") {
		return entityType
	}
	return entityType + ":progress"
}

func toString(v any) string {
	if v == nil {
		return ""
	}
	switch t := v.(type) {
	case string:
		return t
	case []byte:
		return string(t)
	default:
		return fmt.Sprintf("%v", t)
	}
}
