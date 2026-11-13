package persistent

import (
	"database/sql"
	"errors"
	"time"

	"github.com/google/uuid"
)

type OCRRepository struct {
	db *sql.DB
}

func NewOCRRepository(db *sql.DB) *OCRRepository {
	return &OCRRepository{db: db}
}

// CreateOCR inserts a queued OCR job. The external worker is responsible for
// filling ocr_data and advancing the status later.
func (r *OCRRepository) CreateOCR(imageURL string, createdBy uuid.UUID) (*OCRResult, error) {
	id := uuid.New()
	now := time.Now()

	_, err := r.db.Exec(`
		INSERT INTO ocr_results (id, image_url, status, created_by, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6)
	`, id.String(), imageURL, OCRStatusQueued, createdBy.String(), now, now)
	if err != nil {
		return nil, err
	}

	return &OCRResult{
		ID:        id,
		ImageURL:  imageURL,
		Status:    OCRStatusQueued,
		CreatedBy: createdBy,
		CreatedAt: now,
		UpdatedAt: now,
	}, nil
}

// GetByID returns one OCR job, including its ocr_data and error when present.
func (r *OCRRepository) GetByID(id uuid.UUID) (*OCRResult, error) {
	var row OCRResult
	var ocrData, errMsg sql.NullString

	err := r.db.QueryRow(`
		SELECT id, image_url, status, ocr_data, error, created_by, created_at, updated_at
		FROM ocr_results
		WHERE id = $1
	`, id.String()).Scan(
		&row.ID,
		&row.ImageURL,
		&row.Status,
		&ocrData,
		&errMsg,
		&row.CreatedBy,
		&row.CreatedAt,
		&row.UpdatedAt,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrOCRNotFound
	}
	if err != nil {
		return nil, err
	}

	if ocrData.Valid {
		row.OCRData = &ocrData.String
	}
	if errMsg.Valid {
		row.Error = &errMsg.String
	}

	return &row, nil
}

// GetStatus returns the current status of an OCR job.
func (r *OCRRepository) GetStatus(id uuid.UUID) (string, error) {
	var status string
	err := r.db.QueryRow(
		`SELECT status FROM ocr_results WHERE id = $1`,
		id.String(),
	).Scan(&status)
	if errors.Is(err, sql.ErrNoRows) {
		return "", ErrOCRNotFound
	}
	return status, err
}
