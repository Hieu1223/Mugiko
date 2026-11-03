package service

import (
	"errors"
	"strings"

	"github.com/google/uuid"

	"mugiko/internal/modules/core/ai/dto"
	"mugiko/internal/modules/core/ai/exception"
	"mugiko/internal/modules/core/ai/persistent"
)

var ErrPromptRequired = errors.New(exception.MsgPromptRequired)

type LLMService struct {
	repo *persistent.LLMJobRepository
}

func NewLLMService(repo *persistent.LLMJobRepository) *LLMService {
	return &LLMService{repo: repo}
}

// CreateJob creates a queued LLM job. It does not call the LLM.
func (s *LLMService) CreateJob(createdBy uuid.UUID, req dto.CreateLLMJobRequest) (*dto.LLMJobResponse, error) {
	prompt := strings.TrimSpace(req.Prompt)
	if prompt == "" {
		return nil, ErrPromptRequired
	}

	job, err := s.repo.Create(prompt, createdBy)
	if err != nil {
		return nil, err
	}

	return toResponse(job), nil
}

// GetJob returns one LLM job with its current result and status.
func (s *LLMService) GetJob(id uuid.UUID) (*dto.LLMJobResponse, error) {
	job, err := s.repo.GetByID(id)
	if err != nil {
		return nil, err
	}
	return toResponse(job), nil
}

// GetJobStatus returns the current status of a queued or finished LLM job.
func (s *LLMService) GetJobStatus(id uuid.UUID) (string, error) {
	return s.repo.GetStatus(id)
}

func toResponse(job *persistent.LLMJob) *dto.LLMJobResponse {
	return &dto.LLMJobResponse{
		ID:        job.ID,
		Prompt:    job.Prompt,
		Response:  job.Response,
		Status:    job.Status,
		Error:     job.Error,
		CreatedBy: job.CreatedBy,
		CreatedAt: job.CreatedAt,
		UpdatedAt: job.UpdatedAt,
	}
}
