"""Web Novel API routes - single router including all sub-routers."""
from fastapi import APIRouter

from .routes import novel_router

# Create a single router that includes all web_novel sub-routers
router = APIRouter()
router.include_router(novel_router)

__all__ = ["router"]