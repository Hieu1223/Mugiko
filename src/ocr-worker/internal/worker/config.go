package worker

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	defaultNIMParseURL = "https://ai.api.nvidia.com/v1/retrieval/nvidia/nemotron-3.5-parse/parse"
	defaultNIMTimeout  = 120 * time.Second
	defaultMaxImage    = 20 * 1024 * 1024 // 20 MB

	ocrJobsStream  = "ocr_jobs"
	ocrProgressStream = "ocr_progress"
)

type Config struct {
	DATABASEURL         string
	RedisURL            string
	ConsumerGroup       string
	ConsumerName        string
	OCRJobsStream       string
	ProgressTTL         time.Duration
	NIMAPIKeysFile      string
	NIMParseURL         string
	NIMTimeout          time.Duration
	MaxOutputTokens     int
	MaxImageBytes       int64
	ReadBlockMs         int
	ClaimIdleMs         int
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
	group := os.Getenv("OCR_CONSUMER_GROUP")
	if group == "" {
		group = "ocr-workers"
	}
	consumer := os.Getenv("OCR_CONSUMER_NAME")
	if consumer == "" {
		consumer = "ocr-worker-1"
	}
	jobsStream := os.Getenv("OCR_JOBS_STREAM")
	if jobsStream == "" {
		jobsStream = ocrJobsStream
	}
	ttlSecs := 86400
	if v := os.Getenv("PROGRESS_TTL_SECONDS"); v != "" {
		fmt.Sscanf(v, "%d", &ttlSecs)
	}
	parseURL := os.Getenv("NVIDIA_NIM_PARSE_URL")
	if parseURL == "" {
		parseURL = defaultNIMParseURL
	}
	timeout := defaultNIMTimeout
	if v := os.Getenv("NVIDIA_NIM_TIMEOUT_SECONDS"); v != "" {
		var secs float64
		fmt.Sscanf(v, "%f", &secs)
		if secs > 0 {
			timeout = time.Duration(secs) * time.Second
		}
	}
	maxTokens := 1024
	if v := os.Getenv("OCR_MAX_OUTPUT_TOKENS"); v != "" {
		fmt.Sscanf(v, "%d", &maxTokens)
	}
	var maxImage int64 = defaultMaxImage
	if v := os.Getenv("OCR_MAX_IMAGE_BYTES"); v != "" {
		if parsed, err := strconv.ParseInt(v, 10, 64); err == nil && parsed > 0 {
			maxImage = parsed
		}
	}
	keysFile := os.Getenv("NVIDIA_API_KEYS_FILE")
	if keysFile == "" {
		keysFile = "nim.txt"
	}
	readBlock := 5000
	if v := os.Getenv("OCR_READ_BLOCK_MS"); v != "" {
		fmt.Sscanf(v, "%d", &readBlock)
	}
	claimIdle := 300000
	if v := os.Getenv("OCR_CLAIM_IDLE_MS"); v != "" {
		fmt.Sscanf(v, "%d", &claimIdle)
	}

	// Validate Redis URL can be parsed.
	if _, err := redis.ParseURL(redisURL); err != nil {
		return nil, fmt.Errorf("invalid REDIS_URL: %w", err)
	}

	return &Config{
		DATABASEURL:     databaseURL,
		RedisURL:        redisURL,
		ConsumerGroup:   group,
		ConsumerName:    consumer,
		OCRJobsStream:   jobsStream,
		ProgressTTL:     time.Duration(ttlSecs) * time.Second,
		NIMAPIKeysFile:  keysFile,
		NIMParseURL:     strings.TrimRight(parseURL, "/"),
		NIMTimeout:      timeout,
		MaxOutputTokens: maxTokens,
		MaxImageBytes:   maxImage,
		ReadBlockMs:     readBlock,
		ClaimIdleMs:     claimIdle,
	}, nil
}
