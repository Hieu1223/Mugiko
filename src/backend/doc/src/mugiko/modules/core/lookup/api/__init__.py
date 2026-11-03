"""Lookup API routes - single router including all sub-routers."""
from fastapi import APIRouter

from .routes.lookup import router as lookup_router

# Create a single router that includes all lookup sub-routers
router = APIRouter()
router.include_router(lookup_router)

__all__ = ["router"]