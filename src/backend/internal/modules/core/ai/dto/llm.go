package dto

import (
	"time"

	"github.com/google/uuid"
)

// CreateLLMJobRequest is the input for creating an LLM job.
type CreateLLMJobRequest struct {
	Prompt string `json:"prompt"`
}

// LLMJobResponse is the API representation of an LLM job.
type LLMJobResponse struct {
	ID        uuid.UUID `json:"id"`
	Prompt    string    `json:"prompt"`
	Response  *string   `json:"response,omitempty"`
	Status    string    `json:"status"`
	Error     *string   `json:"error,omitempty"`
	CreatedBy uuid.UUID `json:"created_by"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// LLMJobStatusEvent is sent over SSE when an LLM job status changes.
type LLMJobStatusEvent struct {
	JobID  string `json:"job_id"`
	Status string `json:"status"`
}
