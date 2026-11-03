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
}
