"""User Management API routes - single router including all sub-routers."""
from fastapi import APIRouter

from .routes.user_routes import router as user_routes
from .routes.admin_routes import router as admin_routes

# Create a single router that includes all user-management sub-routers
router = APIRouter(prefix="", tags=["user-management"])
router.include_router(user_routes, tags=["user-management"])
router.include_router(admin_routes, tags=["user-management"])

__all__ = ["router"]