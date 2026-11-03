package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strings"
	"time"

	"github.com/google/uuid"

	"mugiko/internal/common/api"
	commonexception "mugiko/internal/common/exception"
	"mugiko/internal/common/persistent"
	"mugiko/internal/modules/core/ai/dto"
	"mugiko/internal/modules/core/ai/exception"
	aipersistent "mugiko/internal/modules/core/ai/persistent"
	"mugiko/internal/modules/core/ai/service"
	"mugiko/internal/modules/core/user/middleware"
)

const llmStatusStreamKey = "llm_status"

type LLMHandler struct {
	svc *service.LLMService
}

func NewLLMHandler(svc *service.LLMService) *LLMHandler {
	return &LLMHandler{svc: svc}
}

// CreateJob queues an LLM job for the external NIM worker.
func (h *LLMHandler) CreateJob(w http.ResponseWriter, r *http.Request) {
	userInfo, ok := middleware.GetUserInfo(r.Context())
	if !ok {
		api.WriteError(w, commonexception.MsgUnauthorized, http.StatusUnauthorized)
		return
	}

	userID, err := uuid.Parse(userInfo.UserID)
	if err != nil {
		api.WriteError(w, commonexception.MsgUnauthorized, http.StatusUnauthorized)
		return
	}

	var req dto.CreateLLMJobRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		api.WriteError(w, commonexception.MsgInvalidRequestBody, http.StatusBadRequest)
		return
	}

	job, err := h.svc.CreateJob(userID, req)
	if err != nil {
		if errors.Is(err, service.ErrPromptRequired) {
			api.WriteError(w, err.Error(), http.StatusBadRequest)
			return
		}
		api.WriteError(w, exception.MsgFailedToCreateJob, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(job)
}

// GetJob returns one LLM job, including its response and error when present.
func (h *LLMHandler) GetJob(w http.ResponseWriter, r *http.Request) {
	jobID, err := uuid.Parse(r.PathValue("job_id"))
	if err != nil {
		api.WriteError(w, exception.MsgInvalidJobID, http.StatusBadRequest)
		return
	}

	job, err := h.svc.GetJob(jobID)
	if err != nil {
		if errors.Is(err, aipersistent.ErrJobNotFound) {
			api.WriteError(w, err.Error(), http.StatusNotFound)
			return
		}
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(job)
}

// StreamJobStatus sends LLM job status changes as Server-Sent Events. It
// emits the current status immediately, then forwards updates from the
// llm_status Redis stream until the job reaches a terminal status.
func (h *LLMHandler) StreamJobStatus(w http.ResponseWriter, r *http.Request) {
	jobID, err := uuid.Parse(r.PathValue("job_id"))
	if err != nil {
		api.WriteError(w, exception.MsgInvalidJobID, http.StatusBadRequest)
		return
	}

	flusher, ok := w.(http.Flusher)
	if !ok {
		api.WriteError(w, exception.MsgStreamingNotSupported, http.StatusInternalServerError)
		return
	}

	events := make(chan persistent.StreamMessage, 16)
	listenErr := make(chan error, 1)
	go func() {
		listenErr <- persistent.ListenRedisStream(r.Context(), llmStatusStreamKey, events)
	}()

	status, err := h.svc.GetJobStatus(jobID)
	if err != nil {
		if errors.Is(err, aipersistent.ErrJobNotFound) {
			api.WriteError(w, err.Error(), http.StatusNotFound)
			return
		}
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(http.StatusOK)
	flusher.Flush()

	lastStatus := ""
	sendStatus := func(status string) bool {
		if status == "" || status == lastStatus {
			return false
		}
		lastStatus = status

		data, err := json.Marshal(dto.LLMJobStatusEvent{
			JobID:  jobID.String(),
			Status: status,
		})
		if err != nil {
			return false
		}

		fmt.Fprintf(w, "event: status\ndata: %s\n\n", data)
		flusher.Flush()

		return status == aipersistent.LLMStatusCompleted || status == aipersistent.LLMStatusFailed
	}

	if sendStatus(status) {
		return
	}

	heartbeat := time.NewTicker(15 * time.Second)
	defer heartbeat.Stop()

	for {
		select {
		case <-r.Context().Done():
			return
		case err := <-listenErr:
			if err != nil && !errors.Is(err, context.Canceled) {
				log.Printf("LLM status stream failed: %v", err)
			}
			return
		case message := <-events:
			id := streamValue(message.Values["id"])
			if !strings.EqualFold(id, jobID.String()) {
				continue
			}
			if sendStatus(streamValue(message.Values["status"])) {
				return
			}
		case <-heartbeat.C:
			fmt.Fprint(w, ": ping\n\n")
			flusher.Flush()
		}
	}
}

func streamValue(value any) string {
	if value == nil {
		return ""
	}

	switch v := value.(type) {
	case string:
		return v
	case []byte:
		return string(v)
	default:
		return fmt.Sprint(v)
	}
}
