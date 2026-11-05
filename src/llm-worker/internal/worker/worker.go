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

const (
	defaultNIMBaseURL = "https://integrate.api.nvidia.com/v1"
	defaultNIMModel   = "nvidia/nemotron-3-ultra-550b-a55b"
	defaultNIMTimeout = 120 * time.Second

	chatProgressStream = "chat_progress"
	llmProgressStream  = "llm_progress"
)

type Config struct {
	DATABASEURL     string
	RedisURL        string
	ConsumerGroup   string
	ConsumerName    string
	ChatJobsStream  string
	LLMJobsStream   string
	ProgressTTL     time.Duration
	NIMBaseURL      string
	NIMModel        string
	NIMTemperature  float64
	NIMMaxTokens    int
	NIMTimeout      time.Duration
	NIMKeysFile     string
	ReadBlockMs     int
	ClaimIdleMs     int
	PollInterval    time.Duration
}

func groupAlreadyExists(err error) bool {
	return err != nil && strings.Contains(err.Error(), "BUSYGROUP")
}

func groupMissing(err error) bool {
	return err != nil && strings.Contains(err.Error(), "NOGROUP")
}

func LoadConfig() (*Config, error) {
	databaseURL := os.Getenv("DATABASE_URL")
	if databaseURL == "" {
		return nil, fmt.Errorf("DATABASE_URL is required")
	}
	redisURL := os.Getenv("REDIS_URL")
	if redisURL == "" {
		redisURL = "redis://localhost:6379/0"
	}
	group := os.Getenv("LLM_CONSUMER_GROUP")
	if group == "" {
		group = "llm-workers"
	}
	consumer := os.Getenv("LLM_CONSUMER_NAME")
	if consumer == "" {
		consumer = "llm-worker-1"
	}
	chatJobs := os.Getenv("LLM_CHAT_JOBS_STREAM")
	if chatJobs == "" {
		chatJobs = "chat_jobs"
	}
	llmJobs := os.Getenv("LLM_JOBS_STREAM")
	if llmJobs == "" {
		llmJobs = "llm_jobs"
	}
	ttlSecs := 86400
	if v := os.Getenv("PROGRESS_TTL_SECONDS"); v != "" {
		fmt.Sscanf(v, "%d", &ttlSecs)
	}
	baseURL := os.Getenv("NVIDIA_NIM_BASE_URL")
	if baseURL == "" {
		baseURL = defaultNIMBaseURL
	}
	model := os.Getenv("NVIDIA_NIM_MODEL")
	if model == "" {
		model = defaultNIMModel
	}
	temperature := 0.2
	if v := os.Getenv("NVIDIA_NIM_TEMPERATURE"); v != "" {
		fmt.Sscanf(v, "%f", &temperature)
	}
	maxTokens := 4096
	if v := os.Getenv("NVIDIA_NIM_MAX_TOKENS"); v != "" {
		fmt.Sscanf(v, "%d", &maxTokens)
	}
	timeout := defaultNIMTimeout
	if v := os.Getenv("NVIDIA_NIM_TIMEOUT_SECONDS"); v != "" {
		var secs float64
		fmt.Sscanf(v, "%f", &secs)
		if secs > 0 {
			timeout = time.Duration(secs) * time.Second
		}
	}
	keysFile := os.Getenv("NVIDIA_API_KEYS_FILE")
	if keysFile == "" {
		keysFile = "nim.txt"
	}
	readBlock := 5000
	if v := os.Getenv("LLM_READ_BLOCK_MS"); v != "" {
		fmt.Sscanf(v, "%d", &readBlock)
	}
	claimIdle := 300000
	if v := os.Getenv("LLM_CLAIM_IDLE_MS"); v != "" {
		fmt.Sscanf(v, "%d", &claimIdle)
	}
	pollInterval := 2 * time.Second
	if v := os.Getenv("LLM_POLL_INTERVAL_MS"); v != "" {
		var ms int
		fmt.Sscanf(v, "%d", &ms)
		if ms > 0 {
			pollInterval = time.Duration(ms) * time.Millisecond
		}
	}
	return &Config{
		DATABASEURL:    databaseURL,
		RedisURL:       redisURL,
		ConsumerGroup:  group,
		ConsumerName:   consumer,
		ChatJobsStream: chatJobs,
		LLMJobsStream:  llmJobs,
		ProgressTTL:    time.Duration(ttlSecs) * time.Second,
		NIMBaseURL:     baseURL,
		NIMModel:       model,
		NIMTemperature: temperature,
		NIMMaxTokens:   maxTokens,
		NIMTimeout:     timeout,
		NIMKeysFile:    keysFile,
		ReadBlockMs:    readBlock,
		ClaimIdleMs:    claimIdle,
		PollInterval:   pollInterval,
	}, nil
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

	// Retry Ping with backoff so the worker waits for PostgreSQL to be ready.
	const maxAttempts = 30
	const retryDelay = 2 * time.Second
	for attempt := 1; attempt <= maxAttempts; attempt++ {
		if err = db.Ping(); err == nil {
			break
		}
		log.Printf("llm worker: waiting for database to be ready (attempt %d/%d): %v", attempt, maxAttempts, err)
		select {
		case <-time.After(retryDelay):
		}
	}
	if err != nil {
		return nil, fmt.Errorf("llm worker: failed to connect to database: %w", err)
	}
	redisClient := redis.NewClient(&redis.Options{
		Addr: mustParseRedisAddr(cfg.RedisURL),
	})

	keys, err := loadAPIKeys(cfg.NIMKeysFile)
	if err != nil {
		return nil, err
	}
	nim, err := NewNIMClient(keys, cfg.NIMBaseURL, cfg.NIMModel, cfg.NIMTemperature, cfg.NIMMaxTokens, cfg.NIMTimeout)
	if err != nil {
		return nil, err
	}
	return &Worker{cfg: cfg, db: db, redis: redisClient, nim: nim, keys: keys}, nil
}

func mustParseRedisAddr(redisURL string) string {
	addr := strings.TrimPrefix(redisURL, "redis://")
	if i := strings.Index(addr, "/"); i >= 0 {
		addr = addr[:i]
	}
	return addr
}

func loadAPIKeys(path string) ([]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
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
		return nil, fmt.Errorf("no NIM API keys in %s", path)
	}
	return keys, nil
}

func (w *Worker) ensureGroup(ctx context.Context, stream string) error {
	_, err := w.redis.Do(ctx, "XGROUP", "CREATE", stream, w.cfg.ConsumerGroup, "0", "MKSTREAM").Result()
	if err != nil {
		if strings.Contains(err.Error(), "BUSYGROUP") {
			return nil
		}
		return err
	}
	return nil
}

func (w *Worker) Run(ctx context.Context) error {
	streams := []string{w.cfg.ChatJobsStream, w.cfg.LLMJobsStream}

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		// Ensure consumer groups exist on every stream before reading.
		for _, s := range streams {
			if err := w.ensureGroup(ctx, s); err != nil {
				log.Printf("llm worker: create group %s on %s: %v", w.cfg.ConsumerGroup, s, err)
			}
		}

		if err := w.reclaimStale(ctx); err != nil {
			log.Printf("llm worker: reclaim stale failed: %v", err)
		}

		streamArgs := []string{}
		for _, s := range streams {
			streamArgs = append(streamArgs, s, ">")
		}
		res, err := w.redis.XReadGroup(ctx, &redis.XReadGroupArgs{
			Group:    w.cfg.ConsumerGroup,
			Consumer: w.cfg.ConsumerName,
			Streams:  streamArgs,
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
				log.Printf("llm worker: group missing, retrying: %v", err)
				time.Sleep(1 * time.Second)
				continue
			}
			log.Printf("llm worker: xreadgroup failed: %v", err)
			time.Sleep(time.Second)
			continue
		}
		for _, stream := range res {
			for _, msg := range stream.Messages {
				if err := w.handleJob(ctx, stream.Stream, msg); err != nil {
					log.Printf("llm worker: handle job %s on %s: %v", msg.ID, stream.Stream, err)
					continue
				}
				if err := w.redis.XAck(ctx, stream.Stream, w.cfg.ConsumerGroup, msg.ID).Err(); err != nil {
					log.Printf("llm worker: ack %s on %s: %v", msg.ID, stream.Stream, err)
				}
			}
		}
	}
}

func (w *Worker) reclaimStale(ctx context.Context) error {
	for _, s := range []string{w.cfg.ChatJobsStream, w.cfg.LLMJobsStream} {
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
				continue
			}
			return err
		}
		for _, msg := range messages {
			if err := w.handleJob(ctx, s, msg); err != nil {
				log.Printf("llm worker: reclaim handle %s on %s: %v", msg.ID, s, err)
				continue
			}
			if err := w.redis.XAck(ctx, s, w.cfg.ConsumerGroup, msg.ID).Err(); err != nil {
				log.Printf("llm worker: reclaim ack %s on %s: %v", msg.ID, s, err)
			}
		}
	}
	return nil
}

type jobRecord struct {
	ID                 string `json:"id"`
	ConversationID     string `json:"conversation_id"`
	Role               string `json:"role"`
	Content            string `json:"content"`
	Prompt             string `json:"prompt"`
	Status             string `json:"status"`
	CreatedBy          string `json:"created_by"`
	AssistantMessageID string `json:"assistant_message_id"`
}

func (w *Worker) handleJob(ctx context.Context, stream string, msg redis.XMessage) error {
	record := extractRecord(msg.Values)
	if record.ID == "" {
		return fmt.Errorf("job record missing id")
	}

	switch stream {
	case w.cfg.ChatJobsStream:
		return w.handleChatJob(ctx, record)
	case w.cfg.LLMJobsStream:
		return w.handleLLMJob(ctx, record)
	default:
		return fmt.Errorf("unknown stream %s", stream)
	}
}

func extractRecord(values map[string]any) jobRecord {
	var rec jobRecord
	if raw, ok := values["record"]; ok {
		b, err := json.Marshal(raw)
		if err == nil {
			_ = json.Unmarshal(b, &rec)
		}
		return rec
	}
	if id, ok := values["id"]; ok {
		rec.ID = fmt.Sprint(id)
	}
	if conv, ok := values["conversation_id"]; ok {
		rec.ConversationID = fmt.Sprint(conv)
	}
	if role, ok := values["role"]; ok {
		rec.Role = fmt.Sprint(role)
	}
	if content, ok := values["content"]; ok {
		rec.Content = fmt.Sprint(content)
	}
	if prompt, ok := values["prompt"]; ok {
		rec.Prompt = fmt.Sprint(prompt)
	}
	if status, ok := values["status"]; ok {
		rec.Status = fmt.Sprint(status)
	}
	return rec
}

func (w *Worker) handleChatJob(ctx context.Context, rec jobRecord) error {
	msgID := rec.ID
	convID := rec.ConversationID

	var dbConvID string
	err := w.db.QueryRowContext(ctx, `
		UPDATE messages
		SET status='processing', updated_at=now()
		WHERE id=$1 AND role='user' AND status='queued'
		RETURNING conversation_id
	`, msgID).Scan(&dbConvID)
	if err != nil {
		if err == sql.ErrNoRows {
			log.Printf("llm worker: chat job %s already claimed or not queued", msgID)
			return nil
		}
		return err
	}
	if convID == "" {
		convID = dbConvID
	}

	w.publishProgress(ctx, "chat", msgID, "processing", map[string]any{
		"message_id":      msgID,
		"conversation_id": convID,
		"status":          "processing",
	})

	messages, err := w.fetchConversationMessages(ctx, convID, 20)
	if err != nil {
		w.failChatJob(ctx, msgID, convID, err.Error())
		return err
	}

	reply, err := w.nim.Chat(ctx, messages)
	if err != nil {
		w.failChatJob(ctx, msgID, convID, err.Error())
		return err
	}

	assistantID, err := w.persistAssistantMessage(ctx, convID, msgID, reply)
	if err != nil {
		w.failChatJob(ctx, msgID, convID, err.Error())
		return err
	}

	w.publishProgress(ctx, "chat", msgID, "completed", map[string]any{
		"message_id":         msgID,
		"conversation_id":    convID,
		"status":             "completed",
		"assistant_message_id": assistantID,
	})
	return nil
}

func (w *Worker) failChatJob(ctx context.Context, msgID, convID, errMsg string) {
	_, _ = w.db.ExecContext(ctx, `
		UPDATE messages SET status='failed', error=$1, updated_at=now() WHERE id=$2 AND role='user'
	`, errMsg, msgID)
	w.publishProgress(ctx, "chat", msgID, "failed", map[string]any{
		"message_id":      msgID,
		"conversation_id": convID,
		"status":          "failed",
		"error":           errMsg,
	})
}

func (w *Worker) fetchConversationMessages(ctx context.Context, convID string, limit int) ([]chatMessage, error) {
	rows, err := w.db.QueryContext(ctx, `
		SELECT role, content FROM messages
		WHERE conversation_id=$1
		ORDER BY created_at ASC
		LIMIT $2
	`, convID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []chatMessage
	for rows.Next() {
		var role, content string
		if err := rows.Scan(&role, &content); err != nil {
			return nil, err
		}
		out = append(out, chatMessage{Role: role, Content: content})
	}
	return out, rows.Err()
}

func (w *Worker) persistAssistantMessage(ctx context.Context, convID, userMsgID, content string) (string, error) {
	tx, err := w.db.BeginTx(ctx, nil)
	if err != nil {
		return "", err
	}
	defer func() { _ = tx.Rollback() }()

	assistantID := newID()
	_, err = tx.ExecContext(ctx, `
		INSERT INTO messages (id, conversation_id, role, content, status, assistant_message_id, created_at, updated_at)
		VALUES ($1, $2, 'assistant', $3, 'completed', $4, now(), now())
	`, assistantID, convID, content, assistantID)
	if err != nil {
		return "", err
	}
	_, err = tx.ExecContext(ctx, `
		UPDATE messages
		SET status='completed', assistant_message_id=$1, updated_at=now()
		WHERE id=$2 AND role='user'
	`, assistantID, userMsgID)
	if err != nil {
		return "", err
	}
	_, err = tx.ExecContext(ctx, `
		UPDATE conversations SET updated_at=now() WHERE id=$1
	`, convID)
	if err != nil {
		return "", err
	}
	if err := tx.Commit(); err != nil {
		return "", err
	}
	return assistantID, nil
}

func (w *Worker) handleLLMJob(ctx context.Context, rec jobRecord) error {
	jobID := rec.ID
	prompt := rec.Prompt
	if prompt == "" {
		prompt = rec.Content
	}

	var createdBy string
	err := w.db.QueryRowContext(ctx, `
		UPDATE llm_jobs
		SET status='processing', updated_at=now()
		WHERE id=$1 AND status='queued'
		RETURNING created_by
	`, jobID).Scan(&createdBy)
	if err != nil {
		if err == sql.ErrNoRows {
			log.Printf("llm worker: llm job %s already claimed or not queued", jobID)
			return nil
		}
		return err
	}

	w.publishProgress(ctx, "llm", jobID, "processing", map[string]any{
		"job_id":     jobID,
		"status":     "processing",
		"created_by": createdBy,
	})

	messages := []chatMessage{{Role: "user", Content: prompt}}
	reply, err := w.nim.Chat(ctx, messages)
	if err != nil {
		w.failLLMJob(ctx, jobID, err.Error())
		return err
	}

	_, err = w.db.ExecContext(ctx, `
		UPDATE llm_jobs
		SET response=$1, status='completed', updated_at=now()
		WHERE id=$2
	`, reply, jobID)
	if err != nil {
		w.failLLMJob(ctx, jobID, err.Error())
		return err
	}
	w.publishProgress(ctx, "llm", jobID, "completed", map[string]any{
		"job_id":     jobID,
		"status":     "completed",
		"created_by": createdBy,
	})
	return nil
}

func (w *Worker) failLLMJob(ctx context.Context, jobID, errMsg string) {
	_, _ = w.db.ExecContext(ctx, `
		UPDATE llm_jobs SET status='failed', error=$1, updated_at=now() WHERE id=$2
	`, errMsg, jobID)
	w.publishProgress(ctx, "llm", jobID, "failed", map[string]any{
		"job_id":  jobID,
		"status":  "failed",
		"error":   errMsg,
	})
}

func (w *Worker) publishProgress(ctx context.Context, entityType, entityID, status string, extra map[string]any) {
	stream := chatProgressStream
	if entityType == "llm" {
		stream = llmProgressStream
	}
	values := map[string]any{
		"entity_type": entityType,
		"entity_id":   entityID,
		"status":      status,
	}
	for k, v := range extra {
		values[k] = v
	}
	if err := w.redis.XAdd(ctx, &redis.XAddArgs{
		Stream:       stream,
		MaxLen:       10000,
		Values:       values,
	}).Err(); err != nil {
		log.Printf("llm worker: publish progress %s/%s: %v", stream, entityID, err)
	}
}

func newID() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("%d", time.Now().UnixNano())
	}
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:])
}
