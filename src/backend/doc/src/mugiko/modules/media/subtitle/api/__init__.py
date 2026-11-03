"""Subtitle API routes - single router including all sub-routers."""
from fastapi import APIRouter

from .routes.providers import router as subtitle_providers_router
from .routes.subtitles import router as subtitle_router
from .routes.settings import router as user_subtitle_settings_router
from .routes.state import router as subtitle_state_router

# Create a single router that includes all subtitle sub-routers
router = APIRouter()
router.include_router(subtitle_providers_router)
router.include_router(subtitle_router)
router.include_router(user_subtitle_settings_router)
router.include_router(subtitle_state_router)

__all__ = ["router"]