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
	"mugiko/internal/modules/core/user/middleware"
	"mugiko/internal/modules/media/ocr/dto"
	"mugiko/internal/modules/media/ocr/exception"
	ocrpersistent "mugiko/internal/modules/media/ocr/persistent"
	"mugiko/internal/modules/media/ocr/service"
)

type OCRHandler struct {
	svc *service.OCRService
}

func NewOCRHandler(svc *service.OCRService) *OCRHandler {
	return &OCRHandler{svc: svc}
}

func (h *OCRHandler) CreateOCR(w http.ResponseWriter, r *http.Request) {
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

	var req dto.OCRCreate
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		api.WriteError(w, commonexception.MsgInvalidRequestBody, http.StatusBadRequest)
		return
	}

	result, err := h.svc.CreateOCR(userID, req)
	if err != nil {
		if errors.Is(err, service.ErrInvalidImageURL) {
			api.WriteError(w, err.Error(), http.StatusBadRequest)
			return
		}

		api.WriteError(w, exception.MsgFailedToCreateOCRJob, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(result)
}

// GetOCR returns one OCR job, including its ocr_data and error when present.
func (h *OCRHandler) GetOCR(w http.ResponseWriter, r *http.Request) {
	ocrID, err := uuid.Parse(r.PathValue("ocr_id"))
	if err != nil {
		api.WriteError(w, exception.MsgInvalidOCRID, http.StatusBadRequest)
		return
	}

	job, err := h.svc.GetOCR(ocrID)
	if err != nil {
		if errors.Is(err, ocrpersistent.ErrOCRNotFound) {
			api.WriteError(w, exception.MsgOCRNotFound, http.StatusNotFound)
			return
		}
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(job)
}

// StreamOCRStatus sends OCR job status changes as Server-Sent Events.
// It subscribes to the Pub/Sub channel for the progress key first, reads the
// current status from the DB as a snapshot, then forwards live updates.
// Payload preserved: {ocr_id, status}.
func (h *OCRHandler) StreamOCRStatus(w http.ResponseWriter, r *http.Request) {
	ocrIDStr := r.PathValue("ocr_id")
	ocrID, err := uuid.Parse(ocrIDStr)
	if err != nil {
		api.WriteError(w, exception.MsgInvalidOCRID, http.StatusBadRequest)
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
	channel := "ocr:progress:" + ocrID.String()
	pubsub := client.Subscribe(r.Context(), channel)
	defer pubsub.Close()

	status, err := h.svc.GetOCRStatus(ocrID)
	if err != nil {
		if errors.Is(err, ocrpersistent.ErrOCRNotFound) {
			api.WriteError(w, exception.MsgOCRNotFound, http.StatusNotFound)
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

		data, err := json.Marshal(dto.OCRStatusEvent{
			OCRID:  ocrID.String(),
			Status: status,
		})
		if err != nil {
			return false
		}

		fmt.Fprintf(w, "event: status\ndata: %s\n\n", data)
		flusher.Flush()

		return status == ocrpersistent.OCRStatusCompleted || status == ocrpersistent.OCRStatusFailed
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
			// DB heartbeat reconciliation: reread authoritative status.
			if cur, err := h.svc.GetOCRStatus(ocrID); err == nil {
				if sendStatus(cur) {
					return
				}
			}
		}
	}
}
