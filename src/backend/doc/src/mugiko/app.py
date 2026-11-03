"""Create and configure the FastAPI application."""
import os
import sys
import uuid
import time
from pathlib import Path


from contextlib import asynccontextmanager
from fastapi import FastAPI, Request,APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from mugiko.common.utils.datetime import get_utc_now
from mugiko.modules.core.user_management.api import router as user_management_router
from mugiko.modules.media.subtitle.api import router as subtitle_router
from mugiko.modules.core.lookup.api import router as lookup_router
from mugiko.modules.core.job.api import job_router
from mugiko.modules.core.word_deck.api import router as word_deck_router
from mugiko.modules.media.web_novel.api import router as web_novel_router
from mugiko.modules.media.manga.api import router as manga_router
from mugiko.modules.core.ai.api import router as ai_router
from mugiko.modules.core.user_management.middleware.auth_context import AuthContextMiddleware
from mugiko.common.persistent.session import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Mugiko API",
        description="FastAPI Modular App with User Management",
        version="0.1.0",
        lifespan=lifespan,
        swagger_ui_parameters={"persistAuthorization": True},
    )

    # Add HTTP Bearer security scheme to OpenAPI
    from fastapi.openapi.utils import get_openapi
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        openapi_schema["components"]["securitySchemes"] = {
            "HTTPBearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Enter token as: `user-<firebase_id_token>`, `admin-<admin_token>`, or `anonymous-<random>`"
            }
        }
        # Apply security globally (can be overridden per-route)
        openapi_schema["security"] = [{"HTTPBearer": []}]
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    app.openapi = custom_openapi

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth context middleware (applies to all routes except register)
    app.add_middleware(AuthContextMiddleware)
    api_router = APIRouter(prefix="/api/v1")
    # Include routers directly
    api_router.include_router(user_management_router)
    api_router.include_router(subtitle_router)
    api_router.include_router(lookup_router)
    api_router.include_router(job_router)
    api_router.include_router(word_deck_router)
    api_router.include_router(web_novel_router)
    api_router.include_router(manga_router)
    api_router.include_router(ai_router)
    app.include_router(api_router)

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "timestamp": get_utc_now().isoformat()}

    # Add global exception handler for structured error responses
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        trace_id = getattr(request.state, 'trace_id', 'unknown')
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "error": str(exc),
                "type": type(exc).__name__,
                "trace_id": trace_id,
            },
        )

    return app


app = create_app()
