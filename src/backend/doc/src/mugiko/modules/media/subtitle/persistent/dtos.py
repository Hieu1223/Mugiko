"""Persistent layer DTOs for subtitle module."""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum


class ProviderKind(str, Enum):
    REMOTE = "remote"
    YOUTUBE = "youtube"


class SubtitleProviderDTO(BaseModel):
    id: UUID
    name: str
    kind: ProviderKind
    base_url: Optional[str]
    is_active: bool
    last_synced_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubtitleProviderServiceDTO(BaseModel):
    id: UUID
    provider_id: UUID
    service_key: str
    name: str
    options: Optional[Dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SubtitleSegmentDTO(BaseModel):
    id: UUID
    subtitle_id: UUID
    idx: int
    start_ms: int
    end_ms: int
    words: Optional[List[Dict[str, Any]]]
    created_at: datetime

    class Config:
        from_attributes = True


class SubtitleDTO(BaseModel):
    id: UUID
    video_id: str
    video_url: str
    provider_id: UUID
    service_id: UUID
    created_by: UUID
    created_at: datetime
    segments: List[SubtitleSegmentDTO] = []

    class Config:
        from_attributes = True


class SubtitleAccessDTO(BaseModel):
    user_id: UUID
    subtitle_id: UUID
    last_accessed_at: datetime

    class Config:
        from_attributes = True


class UserSettingsDTO(BaseModel):
    user_id: UUID
    schema_version: int
    data: Dict[str, Any]
    updated_at: datetime

    class Config:
        from_attributes = True


class SubtitleUserStateDTO(BaseModel):
    user_id: UUID
    subtitle_id: UUID
    schema_version: int
    data: Dict[str, Any]
    updated_at: datetime

    class Config:
        from_attributes = True