"""User management API schemas package."""
from .profile import (
    UserProfileBase,
    UserProfileCreate,
    UserProfileUpdate,
    UserProfileResponse,
)
from .auth import RegisterRequest, RegisterResponse
from .admin import AdminUserListResponse, AdminUserDetailResponse, UpdateRoleRequest

__all__ = [
    "UserProfileBase",
    "UserProfileCreate",
    "UserProfileUpdate",
    "UserProfileResponse",
    "RegisterRequest",
    "RegisterResponse",
    "AdminUserListResponse",
    "AdminUserDetailResponse",
    "UpdateRoleRequest",
]