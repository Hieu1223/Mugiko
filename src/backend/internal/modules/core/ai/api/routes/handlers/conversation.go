package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/google/uuid"

	"mugiko/internal/common/api"
	commonexception "mugiko/internal/common/exception"
	"mugiko/internal/common/persistent"
	aipersistent "mugiko/internal/modules/core/ai/persistent"
	"mugiko/internal/modules/core/user/middleware"
)

type ConversationHandler struct {
	repo *aipersistent.ConversationRepository
}

func NewConversationHandler(repo *aipersistent.ConversationRepository) *ConversationHandler {
	return &ConversationHandler{repo: repo}
}

func (h *ConversationHandler) Create(w http.ResponseWriter, r *http.Request) {
	userInfo, ok := middleware.GetUserInfo(r.Context())
	if !ok {
		api.WriteError(w, commonexception.MsgUnauthorized, http.StatusUnauthorized)
		return
	}
	var req struct {
		Title string `json:"title"`
	}
	json.NewDecoder(r.Body).Decode(&req)
	if req.Title == "" {
		req.Title = "New conversation"
	}
	c, err := h.repo.Create(userInfo.UserID, req.Title)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(c)
}

func (h *ConversationHandler) List(w http.ResponseWriter, r *http.Request) {
	userInfo, ok := middleware.GetUserInfo(r.Context())
	if !ok {
		api.WriteError(w, commonexception.MsgUnauthorized, http.StatusUnauthorized)
		return
	}
	cs, err := h.repo.ListByUser(userInfo.UserID)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(cs)
}

func (h *ConversationHandler) Get(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(r.PathValue("conversation_id"))
	if err != nil {
		api.WriteError(w, "invalid conversation id", http.StatusBadRequest)
		return
	}
	c, err := h.repo.GetByID(id)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusNotFound)
		return
	}
	msgs, _ := h.repo.ListMessages(id)
	// Return conversation with messages embedded, matching frontend Conversation type.
	type conversationWithMessages struct {
		*aipersistent.Conversation
		Messages []aipersistent.Message `json:"messages"`
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(conversationWithMessages{Conversation: c, Messages: msgs})
}

func (h *ConversationHandler) Delete(w http.ResponseWriter, r *http.Request) {
	id, err := uuid.Parse(r.PathValue("conversation_id"))
	if err != nil {
		api.WriteError(w, "invalid conversation id", http.StatusBadRequest)
		return
	}
	if err := h.repo.Delete(id); err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (h *ConversationHandler) AddMessage(w http.ResponseWriter, r *http.Request) {
	convID, err := uuid.Parse(r.PathValue("conversation_id"))
	if err != nil {
		api.WriteError(w, "invalid conversation id", http.StatusBadRequest)
		return
	}
	var req struct {
		Role    string `json:"role"`
		Content string `json:"content"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		api.WriteError(w, commonexception.MsgInvalidRequestBody, http.StatusBadRequest)
		return
	}
	if req.Role == "" {
		req.Role = "user"
	}
	status := "completed"
	if req.Role == "user" {
		status = "queued"
	}
	m, err := h.repo.AddMessage(convID, req.Role, req.Content, status)
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(m)
}

func (h *ConversationHandler) StreamMessageProgress(w http.ResponseWriter, r *http.Request) {
	messageID, err := uuid.Parse(r.PathValue("message_id"))
	if err != nil {
		api.WriteError(w, "invalid message id", http.StatusBadRequest)
		return
	}
	flusher, ok := w.(http.Flusher)
	if !ok {
		api.WriteError(w, "streaming not supported", http.StatusInternalServerError)
		return
	}
	client, err := persistent.GetRedisClient()
	if err != nil {
		api.WriteError(w, err.Error(), http.StatusInternalServerError)
		return
	}
	pubsub := client.Subscribe(r.Context(), "chat:progress:"+messageID.String())
	defer pubsub.Close()

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.WriteHeader(http.StatusOK)
	flusher.Flush()

	ch := pubsub.Channel()
	heartbeat := time.NewTicker(15 * time.Second)
	defer heartbeat.Stop()

	for {
		select {
		case <-r.Context().Done():
			return
		case msg := <-ch:
			fmt.Fprintf(w, "data: %s\n\n", msg.Payload)
			flusher.Flush()
		case <-heartbeat.C:
			fmt.Fprint(w, ": ping\n\n")
			flusher.Flush()
		}
	}
}