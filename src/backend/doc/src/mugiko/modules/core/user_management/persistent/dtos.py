"""DTOs for the persistent layer."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Optional

from mugiko.modules.core.user_management.persistent.models import Role, AuthType


@dataclass
class UserAuthDTO:
    """User auth data transfer object."""
    user_id: UUID
    role: Role
    joined_at: datetime
    auth_type: AuthType
    auth_id: str
    is_active: bool


@dataclass
class UserProfileDTO:
    """User profile data transfer object."""
    user_id: UUID
    name: str
    bio: Optional[str]
    email: Optional[str]


@dataclass
class CreateUserAuthDTO:
    """DTO for creating a user auth."""
    role: Role
    auth_type: AuthType
    auth_id: str
    is_active: bool = True


@dataclass
class CreateUserProfileDTO:
    """DTO for creating a user profile."""
    user_id: UUID
    name: str
    bio: Optional[str] = None
    email: Optional[str] = None