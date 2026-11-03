package persistent

import (
	"errors"
	"time"

	"github.com/google/uuid"

	"mugiko/internal/modules/core/ai/exception"
)

const (
	LLMStatusQueued     = "queued"
	LLMStatusProcessing = "processing"
	LLMStatusCompleted  = "completed"
	LLMStatusFailed     = "failed"
)

// LLMJob is one row in llm_jobs.
type LLMJob struct {
	ID        uuid.UUID `json:"id"`
	Prompt    string    `json:"prompt"`
	Response  *string   `json:"response,omitempty"`
	Status    string    `json:"status"`
	Error     *string   `json:"error,omitempty"`
	CreatedBy uuid.UUID `json:"created_by"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// ErrJobNotFound is returned when an LLM job does not exist.
var ErrJobNotFound = errors.New(exception.MsgJobNotFound)
