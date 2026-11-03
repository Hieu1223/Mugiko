"""Admin schemas."""
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class AdminUserListResponse(BaseModel):
    """Schema for admin user list response."""
    user_id: UUID
    role: str
    auth_type: str
    auth_id: str
    is_active: bool
    joined_at: datetime
    name: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True


class AdminUserDetailResponse(BaseModel):
    """Schema for admin user detail response."""
    user_id: UUID
    role: str
    auth_type: str
    auth_id: str
    is_active: bool
    joined_at: datetime
    name: Optional[str] = None
    bio: Optional[str] = None
    email: Optional[str] = None

    class Config:
        from_attributes = True


class UpdateRoleRequest(BaseModel):
    """Schema for updating user role."""
    role: str = Field(..., pattern="^(anonymous|user|admin)$")