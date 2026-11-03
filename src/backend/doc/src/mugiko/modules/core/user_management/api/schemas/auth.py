"""Auth schemas."""
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """Schema for register request."""
    name: str = Field(..., min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    email: Optional[str] = None


class RegisterResponse(BaseModel):
    """Schema for register response."""
    user_id: UUID
    role: str
    token: str