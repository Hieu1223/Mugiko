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

	"mugiko/internal/modules/core/user/middleware"
	"mugiko/internal/modules/media/subtitle/dto"
	"mugiko/internal/modules/media/subtitle/exception"
	subtitlepersistent "mugiko/internal/modules/media/subtitle/persistent"
	"mugiko/internal/modules/media/subtitle/service"
)

const subtitleStatusStreamKey = "subtitle_status"

type SubtitleHandler struct {
	svc *service.SubtitleService
}

func NewSubtitleHandler(svc *service.SubtitleService) *SubtitleHandler {
	return &SubtitleHandler{svc: svc}
}

// Helper to get user ID from context
func getUserID(r *http.Request) *uuid.UUID {
	if userInfo, ok := middleware.GetUserInfo(r.Context()); ok {
		if userID, err := uuid.Parse(userInfo.UserID); err == nil {
			return &userID
		}
	}
	return nil
}

func (h *SubtitleHandler) ListProviders(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		api.WriteError(w, commonexception.MsgMethodNotAllowed, http.StatusMethodNotAllowed)
		return
	}

	providers, err := h.svc.ListProviders()
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(providers)
}

func (h *SubtitleHandler) CreateProvider(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		api.WriteError(w, commonexception.MsgMethodNotAllowed, http.StatusMethodNotAllowed)
		return
	}

	// Check admin role
	userInfo, ok := middleware.GetUserInfo(r.Context())
	if !ok || userInfo.Role != "admin" {
		api.WriteError(w, commonexception.MsgAdminRequired, http.StatusForbidden)
		return
	}

	var req dto.SubtitleProviderCreate
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		api.WriteError(w, commonexception.MsgInvalidRequestBody, http.StatusBadRequest)
		return
	}

	provider, err := h.svc.CreateProvider(req)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(provider)
}

func (h *SubtitleHandler) CreateSubtitle(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		api.WriteError(w, commonexception.MsgMethodNotAllowed, http.StatusMethodNotAllowed)
		return
	}

	userID := getUserID(r)
	if userID == nil {
		api.WriteError(w, commonexception.MsgUnauthorized, http.StatusUnauthorized)
		return
	}

	var req dto.SubtitleCreate
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		api.WriteError(w, commonexception.MsgInvalidRequestBody, http.StatusBadRequest)
		return
	}

	subtitle, err := h.svc.CreateSubtitle(*userID, req)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(subtitle)
}

func (h *SubtitleHandler) SearchSubtitles(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		api.WriteError(w, commonexception.MsgMethodNotAllowed, http.StatusMethodNotAllowed)
		return
	}

	videoURL := r.URL.Query().Get("video_url")
	if videoURL == "" {
		api.WriteError(w, exception.MsgVideoURLQueryParameterRequired, http.StatusBadRequest)
		return
	}

	limit := 50
	offset := 0
	if l := r.URL.Query().Get("limit"); l != "" {
		fmt.Sscanf(l, "%d", &limit)
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		fmt.Sscanf(o, "%d", &offset)
	}

	subtitles, err := h.svc.SearchSubtitles(videoURL, limit, offset)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(subtitles)
}

func (h *SubtitleHandler) GetSubtitle(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		api.WriteError(w, commonexception.MsgMethodNotAllowed, http.StatusMethodNotAllowed)
		return
	}

	subtitleIDStr := r.PathValue("subtitle_id")
	subtitleID, err := uuid.Parse(subtitleIDStr)
	if err != nil {
		api.WriteError(w, exception.MsgInvalidSubtitleID, http.StatusBadRequest)
		return
	}

	userID := getUserID(r)

	subtitle, err := h.svc.GetSubtitle(subtitleID, userID)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(subtitle)
}

// StreamSubtitleStatus sends subtitle status changes as Server-Sent Events.
// It emits the current status immediately, then forwards updates from the
// subtitle_status Redis stream until the subtitle reaches a terminal status.
func (h *SubtitleHandler) StreamSubtitleStatus(w http.ResponseWriter, r *http.Request) {
	subtitleIDStr := r.PathValue("subtitle_id")
	subtitleID, err := uuid.Parse(subtitleIDStr)
	if err != nil {
		api.WriteError(w, exception.MsgInvalidSubtitleID, http.StatusBadRequest)
		return
	}

	flusher, ok := w.(http.Flusher)
	if !ok {
		api.WriteError(w, "Streaming not supported", http.StatusInternalServerError)
		return
	}

	events := make(chan persistent.StreamMessage, 16)
	listenErr := make(chan error, 1)
	go func() {
		listenErr <- persistent.ListenRedisStream(r.Context(), subtitleStatusStreamKey, events)
	}()

	subtitle, err := h.svc.GetSubtitle(subtitleID, nil)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusNotFound)
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

		data, err := json.Marshal(dto.SubtitleStatusEvent{
			SubtitleID: subtitleID.String(),
			Status:     status,
		})
		if err != nil {
			return false
		}

		fmt.Fprintf(w, "event: status\ndata: %s\n\n", data)
		flusher.Flush()

		return status == subtitlepersistent.SubtitleStatusCompleted || status == subtitlepersistent.SubtitleStatusFailed
	}

	if sendStatus(subtitle.Status) {
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
				log.Printf("Subtitle status stream failed: %v", err)
			}
			return
		case message := <-events:
			id := streamValue(message.Values["id"])
			if !strings.EqualFold(id, subtitleID.String()) {
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

func (h *SubtitleHandler) GetSubtitleSegments(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		api.WriteError(w, commonexception.MsgMethodNotAllowed, http.StatusMethodNotAllowed)
		return
	}

	subtitleIDStr := r.PathValue("subtitle_id")
	subtitleID, err := uuid.Parse(subtitleIDStr)
	if err != nil {
		api.WriteError(w, exception.MsgInvalidSubtitleID, http.StatusBadRequest)
		return
	}

	limit := 100
	offset := 0
	if l := r.URL.Query().Get("limit"); l != "" {
		fmt.Sscanf(l, "%d", &limit)
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		fmt.Sscanf(o, "%d", &offset)
	}

	segments, err := h.svc.GetSubtitleSegments(subtitleID, limit, offset)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(segments)
}

func (h *SubtitleHandler) GetUserSettings(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		api.WriteError(w, commonexception.MsgMethodNotAllowed, http.StatusMethodNotAllowed)
		return
	}

	userID := getUserID(r)
	if userID == nil {
		api.WriteError(w, commonexception.MsgUnauthorized, http.StatusUnauthorized)
		return
	}

	settings, err := h.svc.GetUserSettings(*userID)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(settings)
}

func (h *SubtitleHandler) UpdateUserSettings(w http.ResponseWriter, r *http.Request) {
	if r.Method != "PUT" {
		api.WriteError(w, commonexception.MsgMethodNotAllowed, http.StatusMethodNotAllowed)
		return
	}

	userID := getUserID(r)
	if userID == nil {
		api.WriteError(w, commonexception.MsgUnauthorized, http.StatusUnauthorized)
		return
	}

	var req dto.UserSettingsUpdate
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		api.WriteError(w, commonexception.MsgInvalidRequestBody, http.StatusBadRequest)
		return
	}

	settings, err := h.svc.UpdateUserSettings(*userID, req)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(settings)
}

func (h *SubtitleHandler) GetSubtitleUserState(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		api.WriteError(w, commonexception.MsgMethodNotAllowed, http.StatusMethodNotAllowed)
		return
	}

	userID := getUserID(r)
	if userID == nil {
		api.WriteError(w, commonexception.MsgUnauthorized, http.StatusUnauthorized)
		return
	}

	subtitleIDStr := r.PathValue("subtitle_id")
	subtitleID, err := uuid.Parse(subtitleIDStr)
	if err != nil {
		api.WriteError(w, exception.MsgInvalidSubtitleID, http.StatusBadRequest)
		return
	}

	state, err := h.svc.GetSubtitleUserState(*userID, subtitleID)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(state)
}

func (h *SubtitleHandler) UpdateSubtitleUserState(w http.ResponseWriter, r *http.Request) {
	if r.Method != "PUT" {
		api.WriteError(w, commonexception.MsgMethodNotAllowed, http.StatusMethodNotAllowed)
		return
	}

	userID := getUserID(r)
	if userID == nil {
		api.WriteError(w, commonexception.MsgUnauthorized, http.StatusUnauthorized)
		return
	}

	subtitleIDStr := r.PathValue("subtitle_id")
	subtitleID, err := uuid.Parse(subtitleIDStr)
	if err != nil {
		api.WriteError(w, exception.MsgInvalidSubtitleID, http.StatusBadRequest)
		return
	}

	var req dto.SubtitleUserStateUpdate
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		api.WriteError(w, commonexception.MsgInvalidRequestBody, http.StatusBadRequest)
		return
	}

	state, err := h.svc.UpdateSubtitleUserState(*userID, subtitleID, req)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(state)
}

func (h *SubtitleHandler) GetUserHistory(w http.ResponseWriter, r *http.Request) {
	if r.Method != "GET" {
		api.WriteError(w, commonexception.MsgMethodNotAllowed, http.StatusMethodNotAllowed)
		return
	}

	userID := getUserID(r)
	if userID == nil {
		api.WriteError(w, commonexception.MsgUnauthorized, http.StatusUnauthorized)
		return
	}

	limit := 50
	offset := 0
	if l := r.URL.Query().Get("limit"); l != "" {
		fmt.Sscanf(l, "%d", &limit)
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		fmt.Sscanf(o, "%d", &offset)
	}

	history, err := h.svc.GetUserHistory(*userID, limit, offset)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(history)
}
