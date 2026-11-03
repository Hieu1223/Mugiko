package persistent

import (
	"database/sql"
	"errors"
	"time"

	"github.com/google/uuid"
)

type LLMJobRepository struct {
	db *sql.DB
}

func NewLLMJobRepository(db *sql.DB) *LLMJobRepository {
	return &LLMJobRepository{db: db}
}

// Create inserts a queued LLM job. The external worker is responsible for
// filling response and advancing the status later.
func (r *LLMJobRepository) Create(prompt string, createdBy uuid.UUID) (*LLMJob, error) {
	id := uuid.New()
	now := time.Now()

	_, err := r.db.Exec(`
		INSERT INTO llm_jobs (id, prompt, status, created_by, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6)
	`, id.String(), prompt, LLMStatusQueued, createdBy.String(), now, now)
	if err != nil {
		return nil, err
	}

	return &LLMJob{
		ID:        id,
		Prompt:    prompt,
		Status:    LLMStatusQueued,
		CreatedBy: createdBy,
		CreatedAt: now,
		UpdatedAt: now,
	}, nil
}

// GetByID returns one job, including its response and error when present.
func (r *LLMJobRepository) GetByID(id uuid.UUID) (*LLMJob, error) {
	var job LLMJob
	var response, jobError sql.NullString

	err := r.db.QueryRow(`
		SELECT id, prompt, response, status, error, created_by, created_at, updated_at
		FROM llm_jobs
		WHERE id = $1
	`, id.String()).Scan(
		&job.ID,
		&job.Prompt,
		&response,
		&job.Status,
		&jobError,
		&job.CreatedBy,
		&job.CreatedAt,
		&job.UpdatedAt,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrJobNotFound
	}
	if err != nil {
		return nil, err
	}

	if response.Valid {
		job.Response = &response.String
	}
	if jobError.Valid {
		job.Error = &jobError.String
	}

	return &job, nil
}

// GetStatus returns the current status of one job.
func (r *LLMJobRepository) GetStatus(id uuid.UUID) (string, error) {
	var status string
	err := r.db.QueryRow(
		`SELECT status FROM llm_jobs WHERE id = $1`,
		id.String(),
	).Scan(&status)
	if errors.Is(err, sql.ErrNoRows) {
		return "", ErrJobNotFound
	}
	return status, err
}
