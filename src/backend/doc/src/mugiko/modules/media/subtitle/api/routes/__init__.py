"""Subtitle API routes package."""
from .providers import router as subtitle_providers_router
from .subtitles import router as subtitle_router
from .settings import router as user_subtitle_settings_router
from .state import router as subtitle_state_router

__all__ = [
    "subtitle_providers_router",
    "subtitle_router",
    "user_subtitle_settings_router",
    "subtitle_state_router",
]