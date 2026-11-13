package worker

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strings"
	"time"

	_ "github.com/lib/pq"
	"github.com/redis/go-redis/v9"
)

const defaultNIMBaseURL = "https://integrate.api.nvidia.com/v1"

func groupAlreadyExists(err error) bool {
	return err != nil && strings.Contains(err.Error(), "BUSYGROUP")
}

func groupMissing(err error) bool {
	return err != nil && strings.Contains(err.Error(), "NOGROUP")
}

type Worker struct {
	cfg    *Config
	db     *sql.DB
	redis  *redis.Client
	nim    *NIMClient
	keys   []string
}

func New(cfg *Config) (*Worker, error) {
	db, err := sql.Open("postgres", cfg.DATABASEURL)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(5)

	const maxAttempts = 30
	const retryDelay = 2 * time.Second
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		if err = db.Ping(); err == nil {
			break
		}
		log.Printf("ocr worker: waiting for database to be ready (attempt %d/%d): %v", attempt, maxAttempts, err)
		select {
		case <-time.After(retryDelay):
		}
	}
	if err != nil {
		return nil, fmt.Errorf("ocr worker: failed to connect to database: %w", err)
	}

	addr := strings.TrimPrefix(cfg.RedisURL, "redis://")
	if i := strings.Index(addr, "/"); i >= 0 {
		addr = addr[:i]
	}
	redisClient := redis.NewClient(&redis.Options{
		Addr: addr,
	})

	keys, err := loadAPIKeys(cfg.NIMAPIKeysFile)
	if err != nil {
		return nil, err
	}
	nim, err := NewNIMClient(keys, cfg.NIMParseURL, cfg.NIMTimeout, cfg.MaxImageBytes)
	if err != nil {
		return nil, err
	}
	return &Worker{cfg: cfg, db: db, redis: redisClient, nim: nim, keys: keys}, nil
}

func loadAPIKeys(path string) ([]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		// Fall back to a single NVIDIA_API_KEY env var if the keys file is absent.
		if key := strings.TrimSpace(os.Getenv("NVIDIA_API_KEY")); key != "" {
			return []string{key}, nil
		}
		return nil, err
	}
	var keys []string
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line != "" {
			keys = append(keys, line)
		}
	}
	if len(keys) == 0 {
		if key := strings.TrimSpace(os.Getenv("NVIDIA_API_KEY")); key != "" {
			return []string{key}, nil
		}
		return nil, fmt.Errorf("no NIM API keys in %s", path)
	}
	return keys, nil
}

func (w *Worker) ensureGroup(ctx context.Context) error {
	s := w.cfg.OCRJobsStream
	if _, err := w.redis.XAdd(ctx, &redis.XAddArgs{
		Stream: s,
		Values: map[string]any{"__init": "1"},
	}).Result(); err != nil {
		return fmt.Errorf("xadd %s: %w", s, err)
	}
	if _, err := w.redis.Do(ctx, "XGROUP", "CREATE", s, w.cfg.ConsumerGroup, "0").Result(); err != nil {
		if strings.Contains(err.Error(), "BUSYGROUP") {
			return nil
		}
		return fmt.Errorf("xgroup create %s %s: %w", s, w.cfg.ConsumerGroup, err)
	}
	return nil
}

func (w *Worker) Run(ctx context.Context) error {
	s := w.cfg.OCRJobsStream

	for attempt := 1; attempt <= 30; attempt++ {
		if err := w.ensureGroup(ctx); err == nil {
			break
		}
		log.Printf("ocr worker: waiting for redis stream (attempt %d/30)", attempt)
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(2 * time.Second):
		}
	}

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		res, err := w.redis.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group:    w.cfg.ConsumerGroup,
			Consumer: w.cfg.ConsumerName,
			Streams:  []string{s, ">"},
			Count:    5,
			Block:    time.Duration(w.cfg.ReadBlockMs) * time.Millisecond,
		}).Result()
		if err != nil {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			if err == redis.Nil {
				continue
			}
			if groupMissing(err) {
				log.Printf("ocr worker: group missing on %s, recreating: %v", s, err)
				_ = w.ensureGroup(ctx)
				continue
			}
			log.Printf("ocr worker: xreadgroup failed on %s: %v", s, err)
			continue
		}
		for _, stream := range res {
			for _, msg := range stream.Messages {
				if _, ok := msg.Values["__init"]; ok {
					_ = w.redis.XAck(ctx, s, w.cfg.ConsumerGroup, msg.ID)
					continue
				}
				if err := w.handleJob(ctx, msg); err != nil {
					log.Printf("ocr worker: handle job %s: %v", msg.ID, err)
					continue
				}
				if err := w.redis.XAck(ctx, s, w.cfg.ConsumerGroup, msg.ID).Err(); err != nil {
					log.Printf("ocr worker: ack %s: %v", msg.ID, err)
				}
			}
		}
		if err := w.reclaimStale(ctx); err != nil {
			log.Printf("ocr worker: reclaim stale failed: %v", err)
		}
	}
}

func (w *Worker) reclaimStale(ctx context.Context) error {
	s := w.cfg.OCRJobsStream
	messages, _, err := w.redis.XAutoClaim(ctx, &redis.XAutoClaimArgs{
		Stream:   s,
		Group:    w.cfg.ConsumerGroup,
		Consumer: w.cfg.ConsumerName,
		MinIdle:  time.Duration(w.cfg.ClaimIdleMs) * time.Millisecond,
		Start:    "0-0",
		Count:    10,
	}).Result()
	if err != nil {
		if err == redis.Nil {
			return nil
		}
		return err
	}
	for _, msg := range messages {
		if err := w.handleJob(ctx, msg); err != nil {
			log.Printf("ocr worker: reclaim handle %s: %v", msg.ID, err)
			continue
		}
		if err := w.redis.XAck(ctx, s, w.cfg.ConsumerGroup, msg.ID).Err(); err != nil {
			log.Printf("ocr worker: reclaim ack %s: %v", msg.ID, err)
		}
	}
	return nil
}

type jobRecord struct {
	ID        string `json:"id"`
	ImageURL  string `json:"image_url"`
	Status    string `json:"status"`
	CreatedBy string `json:"created_by"`
}

func extractRecord(values map[string]any) jobRecord {
	var rec jobRecord
	if raw, ok := values["record"]; ok {
		b, err := json.Marshal(raw)
		if err == nil {
			_ = json.Unmarshal(b, &rec)
			return rec
		}
	}
	if id, ok := values["id"]; ok {
		rec.ID = fmt.Sprint(id)
	}
	if url, ok := values["image_url"]; ok {
		rec.ImageURL = fmt.Sprint(url)
	}
	if status, ok := values["status"]; ok {
		rec.Status = fmt.Sprint(status)
	}
	return rec
}

func (w *Worker) handleJob(ctx context.Context, msg redis.XMessage) error {
	record := extractRecord(msg.Values)
	if record.ID == "" {
		return fmt.Errorf("job record missing id")
	}

	var imageURL string
	err := w.db.QueryRowContext(ctx, `
		UPDATE ocr_results
		SET status='processing', error=NULL, updated_at=now()
		WHERE id=$1 AND status='queued'
		RETURNING image_url
	`, record.ID).Scan(&imageURL)
	if err != nil {
		if err == sql.ErrNoRows {
			log.Printf("ocr worker: job %s already claimed or not queued", record.ID)
			return nil
		}
		return err
	}
	if imageURL != "" {
		record.ImageURL = imageURL
	}

	log.Printf("ocr worker: processing job %s image=%s", record.ID, record.ImageURL)

	ocrData, err := w.nim.ParseDocument(ctx, record.ImageURL, w.cfg.MaxOutputTokens)
	if err != nil {
		w.failJob(ctx, record.ID, err.Error())
		return err
	}

	_, err = w.db.ExecContext(ctx, `
		UPDATE ocr_results
		SET ocr_data=$1, status='completed', updated_at=now()
		WHERE id=$2
	`, ocrData, record.ID)
	if err != nil {
		w.failJob(ctx, record.ID, err.Error())
		return err
	}

	log.Printf("ocr worker: completed job %s", record.ID)
	return nil
}

func (w *Worker) failJob(ctx context.Context, jobID, errMsg string) {
	_, _ = w.db.ExecContext(ctx, `
		UPDATE ocr_results SET status='failed', error=$1, updated_at=now() WHERE id=$2
	`, errMsg, jobID)
	log.Printf("ocr worker: failed job %s: %s", jobID, errMsg)
}

func newID() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:])
}
