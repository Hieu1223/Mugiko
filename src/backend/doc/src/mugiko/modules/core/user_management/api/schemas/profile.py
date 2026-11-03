"""Profile schemas."""
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class UserProfileBase(BaseModel):
    """Base user profile schema."""
    name: str = Field(..., min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    email: Optional[str] = None


class UserProfileCreate(UserProfileBase):
    """Schema for creating user profile."""
    pass


class UserProfileUpdate(BaseModel):
    """Schema for updating user profile."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    email: Optional[str] = None


class UserProfileResponse(UserProfileBase):
    """Schema for user profile response."""
    user_id: UUID
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True