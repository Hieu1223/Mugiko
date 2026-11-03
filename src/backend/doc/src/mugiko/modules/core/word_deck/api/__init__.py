"""Word Deck API routes - single router including all sub-routers."""
from fastapi import APIRouter

from .routes import deck_router, word_router, export_router

# Create a single router that includes all word_deck sub-routers
router = APIRouter()
router.include_router(deck_router)
router.include_router(word_router)
router.include_router(export_router)

__all__ = ["router"]