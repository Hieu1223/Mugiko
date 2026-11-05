package handlers

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
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
// subscribes to the Pub/Sub channel for the progress key first, reads the
// current status from the DB as a snapshot, then forwards live updates. The DB
// is used as the authoritative fallback on stream close/failure.
// Payload preserved: {job_id, status}.
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

	client, err := persistent.GetRedisClient()
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}
	channel := "llm:progress:" + jobID.String()
	pubsub := client.Subscribe(r.Context(), channel)
	defer pubsub.Close()

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

	// Snapshot from DB first (authoritative), then live updates via Pub/Sub.
	if sendStatus(status) {
		return
	}

	ch := pubsub.Channel()
	heartbeat := time.NewTicker(15 * time.Second)
	defer heartbeat.Stop()
	reconcile := time.NewTicker(5 * time.Second)
	defer reconcile.Stop()

	for {
		select {
		case <-r.Context().Done():
			return
		case msg := <-ch:
			var raw map[string]any
			if json.Unmarshal([]byte(msg.Payload), &raw) == nil {
				if st, _ := raw["status"].(string); st != "" {
					if sendStatus(st) {
						return
					}
				}
			}
		case <-heartbeat.C:
			fmt.Fprint(w, ": ping\n\n")
			flusher.Flush()
		case <-reconcile.C:
			if cur, err := h.svc.GetJobStatus(jobID); err == nil {
				if sendStatus(cur) {
					return
				}
			}
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
