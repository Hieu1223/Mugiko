package persistent

import (
	"errors"
	"time"

	"github.com/google/uuid"

	"mugiko/internal/modules/media/ocr/exception"
)

const (
	OCRStatusQueued     = "queued"
	OCRStatusProcessing = "processing"
	OCRStatusCompleted  = "completed"
	OCRStatusFailed     = "failed"
)

// OCRResult is one row in ocr_results.
type OCRResult struct {
	ID        uuid.UUID `json:"id"`
	ImageURL  string    `json:"image_url"`
	Status    string    `json:"status"`
	OCRData   *string   `json:"ocr_data,omitempty"`
	Error     *string   `json:"error,omitempty"`
	CreatedBy uuid.UUID `json:"created_by"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// ErrOCRNotFound is returned when an OCR job does not exist.
var ErrOCRNotFound = errors.New(exception.MsgOCRNotFound)
