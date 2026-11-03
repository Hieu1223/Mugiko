"""User management module."""
from fastapi import APIRouter

from mugiko.modules.core.user_management.api.routes import user_routes, admin_routes
from mugiko.modules.core.user_management.middleware.auth_context import AuthContextMiddleware


# Create main router for this module
router = APIRouter()
router.include_router(user_routes.router, prefix="/users")
router.include_router(admin_routes.router, prefix="/admin/users")


__all__ = ["router", "AuthContextMiddleware"]