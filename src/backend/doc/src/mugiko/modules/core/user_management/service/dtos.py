"""DTOs for the service layer."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Optional

from mugiko.modules.core.user_management.persistent.models import Role, AuthType


@dataclass
class AuthContext:
    """Authentication context from middleware."""
    user_id: UUID
    role: Role


@dataclass
class RegisterRequest:
    """Request for user registration."""
    firebase_uid: str
    name: str
    bio: Optional[str] = None
    email: Optional[str] = None


@dataclass
class RegisterResponse:
    """Response for user registration."""
    user_id: UUID
    role: Role
    token: str


@dataclass
class UserProfileResponse:
    """User profile response."""
    user_id: UUID
    name: str
    bio: Optional[str]
    email: Optional[str]
    role: Role
    joined_at: datetime


@dataclass
class UpdateProfileRequest:
    """Request to update profile."""
    name: Optional[str] = None
    bio: Optional[str] = None
    email: Optional[str] = None


@dataclass
class AdminUserListResponse:
    """Admin user list response."""
    user_id: UUID
    role: Role
    auth_type: AuthType
    auth_id: str
    is_active: bool
    joined_at: datetime
    name: Optional[str]
    email: Optional[str]


@dataclass
class AdminUserDetailResponse:
    """Admin user detail response."""
    user_id: UUID
    role: Role
    auth_type: AuthType
    auth_id: str
    is_active: bool
    joined_at: datetime
    name: Optional[str]
    bio: Optional[str]
    email: Optional[str]


@dataclass
class UpdateRoleRequest:
    """Request to update user role."""
    role: Role