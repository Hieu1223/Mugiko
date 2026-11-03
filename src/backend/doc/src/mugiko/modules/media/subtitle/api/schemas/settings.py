"""Settings schemas."""
from pydantic import BaseModel
from typing import Dict, Any
from uuid import UUID
from datetime import datetime


class UserSettingsResponse(BaseModel):
    user_id: UUID
    schema_version: int
    data: Dict[str, Any]
    updated_at: datetime

    class Config:
        from_attributes = True


class UserSettingsUpdate(BaseModel):
    schema_version: int
    data: Dict[str, Any]