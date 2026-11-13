package dto

import (
	"time"

	"github.com/google/uuid"
)

// OCRCreate is the request body for creating an OCR job.
type OCRCreate struct {
	ImageURL string `json:"image_url"`
}

// ParseResult is the parsed document output returned by NVIDIA nemotron-3.5-parse.
type ParseResult struct {
	Content      string     `json:"content"`
	FinishReason string     `json:"finish_reason,omitempty"`
	Usage        ParseUsage `json:"usage,omitempty"`
}

// ParseUsage holds token usage from the NIM response.
type ParseUsage struct {
	OutputTokens int `json:"output_tokens,omitempty"`
}

// OCRStatusEvent is sent over SSE when an OCR job status changes.
type OCRStatusEvent struct {
	OCRID  string `json:"ocr_id"`
	Status string `json:"status"`
}

// OCRResponse is the API representation of an OCR job.
type OCRResponse struct {
	ID        uuid.UUID   `json:"id"`
	ImageURL  string      `json:"image_url"`
	Status    string      `json:"status"`
	OCRData   *ParseResult `json:"ocr_data,omitempty"`
	Error     *string     `json:"error,omitempty"`
	CreatedBy uuid.UUID   `json:"created_by"`
	CreatedAt time.Time   `json:"created_at"`
	UpdatedAt time.Time   `json:"updated_at"`
}
