"""API routes package."""
from .deck_routes import router as deck_router
from .word_routes import router as word_router
from .export_routes import router as export_router

__all__ = ["deck_router", "word_router", "export_router"]