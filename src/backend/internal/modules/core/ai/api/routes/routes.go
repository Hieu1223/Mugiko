package routes

import (
	"database/sql"
	"net/http"

	"mugiko/internal/modules/core/ai/api/routes/handlers"
	"mugiko/internal/modules/core/ai/persistent"
	"mugiko/internal/modules/core/ai/service"
)

func RegisterLLMRoutes(mux *http.ServeMux, db *sql.DB) {
	repo := persistent.NewLLMJobRepository(db)
	svc := service.NewLLMService(repo)
	handler := handlers.NewLLMHandler(svc)

	mux.HandleFunc("POST /api/v1/llm-jobs", handler.CreateJob)
	mux.HandleFunc("GET /api/v1/llm-jobs/{job_id}", handler.GetJob)
	mux.HandleFunc("GET /api/v1/llm-jobs/{job_id}/status", handler.StreamJobStatus)

	// Conversations
	convRepo := persistent.NewConversationRepository(db)
	convHandler := handlers.NewConversationHandler(convRepo)
	mux.HandleFunc("POST /api/v1/ai/conversations", convHandler.Create)
	mux.HandleFunc("GET /api/v1/ai/conversations", convHandler.List)
	mux.HandleFunc("GET /api/v1/ai/conversations/{conversation_id}", convHandler.Get)
	mux.HandleFunc("DELETE /api/v1/ai/conversations/{conversation_id}", convHandler.Delete)
	mux.HandleFunc("POST /api/v1/ai/conversations/{conversation_id}/messages", convHandler.AddMessage)
	mux.HandleFunc("GET /api/v1/ai/conversations/{conversation_id}/messages/{message_id}/progress", convHandler.StreamMessageProgress)
}
