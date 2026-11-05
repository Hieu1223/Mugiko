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

// ensureGroups creates every stream (if missing) and its consumer group
// before any reads happen. Uses XADD to materialize the stream, then
// XGROUP CREATE to register the consumer group at the beginning.
func (u *Updater) ensureGroups(ctx context.Context) error {
	for _, stream := range u.streams {
		err := u.redis.XGroupCreateMkStream(
			ctx,
			stream,
			u.group,
			"0",
		).Err()

		if err != nil {
			if strings.Contains(err.Error(), "BUSYGROUP") {
				continue
			}

			return fmt.Errorf(
				"create consumer group %s on stream %s: %w",
				u.group,
				stream,
				err,
			)
		}

		log.Printf(
			"cache updater: created consumer group %s on stream %s",
			u.group,
			stream,
		)
	}

	return nil
}

func (u *Updater) Run(ctx context.Context) error {
	// Initialize consumer groups before starting consumers.
	initialized := false

	for attempt := 1; attempt <= 30; attempt++ {
		if err := u.ensureGroups(ctx); err == nil {
			initialized = true
			break
		} else {
			log.Printf(
				"cache updater: initialization failed (attempt %d/30): %v",
				attempt,
				err,
			)
		}

		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(2 * time.Second):
		}
	}

	if !initialized {
		return fmt.Errorf("failed to initialize Redis consumer groups")
	}

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		// Read each stream individually to isolate errors.
		for _, streamName := range u.streams {
			res, err := u.redis.XReadGroup(ctx, &redis.XReadGroupArgs{
				Group:    u.group,
				Consumer: u.consumer,
				Streams:  []string{streamName, ">"},
				Count:    10,
				Block:    5 * time.Second,
			}).Result()

			if err != nil {
				if ctx.Err() != nil {
					return ctx.Err()
				}

				if err == redis.Nil {
					continue
				}

				if groupMissing(err) {
					log.Printf(
						"cache updater: consumer group missing: stream=%q group=%q error=%v",
						streamName,
						u.group,
						err,
					)

					if initErr := u.ensureGroups(ctx); initErr != nil {
						log.Printf(
							"cache updater: group recovery failed: %v",
							initErr,
						)
						time.Sleep(time.Second)
					}

					continue
				}

				log.Printf(
					"cache updater: XREADGROUP failed: stream=%q group=%q consumer=%q error=%v",
					streamName,
					u.group,
					u.consumer,
					err,
				)

				time.Sleep(time.Second)
				continue
			}

			for _, stream := range res {
				for _, msg := range stream.Messages {
					// Skip initialization dummy entries.
					if _, ok := msg.Values["__init"]; ok {
						if err := u.redis.XAck(
							ctx,
							stream.Stream,
							u.group,
							msg.ID,
						).Err(); err != nil {
							log.Printf(
								"cache updater: dummy message ack failed: stream=%s id=%s error=%v",
								stream.Stream,
								msg.ID,
								err,
							)
						}
						continue
					}

					if err := u.handle(ctx, stream.Stream, msg); err != nil {
						log.Printf(
							"cache updater: handle failed: stream=%s id=%s error=%v",
							stream.Stream,
							msg.ID,
							err,
						)
						continue
					}

					if err := u.redis.XAck(
						ctx,
						stream.Stream,
						u.group,
						msg.ID,
					).Err(); err != nil {
						log.Printf(
							"cache updater: ack failed: stream=%s id=%s error=%v",
							stream.Stream,
							msg.ID,
							err,
						)
					}
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
