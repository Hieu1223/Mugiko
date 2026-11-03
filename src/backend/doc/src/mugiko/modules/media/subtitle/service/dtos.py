"""Service layer DTOs for subtitle module."""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from enum import Enum


class ProviderKind(str, Enum):
    REMOTE = "remote"
    YOUTUBE = "youtube"


class SubtitleProviderCreate(BaseModel):
    name: str
    kind: ProviderKind
    base_url: Optional[str] = None


class SubtitleProviderResponse(BaseModel):
    id: UUID
    name: str
    kind: ProviderKind
    base_url: Optional[str]
    is_active: bool
    last_synced_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    services: List["SubtitleProviderServiceResponse"] = []

    class Config:
        from_attributes = True


class SubtitleProviderServiceResponse(BaseModel):
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


class SubtitleCreate(BaseModel):
    video_url: str
    provider_id: UUID
    service_key: str


class SubtitleResponse(BaseModel):
    id: UUID
    video_id: str
    video_url: str
    provider_id: UUID
    service_id: UUID
    created_by: UUID
    created_at: datetime
    segments: List["SubtitleSegmentResponse"] = []
    provider: Optional[SubtitleProviderResponse] = None
    service: Optional[SubtitleProviderServiceResponse] = None

    class Config:
        from_attributes = True


class SubtitleSegmentResponse(BaseModel):
    id: UUID
    subtitle_id: UUID
    idx: int
    start_ms: int
    end_ms: int
    words: Optional[List[Dict[str, Any]]]
    created_at: datetime

    class Config:
        from_attributes = True


class SubtitleListResponse(BaseModel):
    id: UUID
    video_id: str
    video_url: str
    provider_id: UUID
    service_id: UUID
    created_by: UUID
    created_at: datetime
    segment_count: int

    class Config:
        from_attributes = True


class SubtitleSearchRequest(BaseModel):
    video_url: str


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


class SubtitleUserStateResponse(BaseModel):
    user_id: UUID
    subtitle_id: UUID
    schema_version: int
    data: Dict[str, Any]
    updated_at: datetime

    class Config:
        from_attributes = True


class SubtitleUserStateUpdate(BaseModel):
    schema_version: int
    data: Dict[str, Any]


# Update forward references
SubtitleProviderResponse.model_rebuild()
SubtitleResponse.model_rebuild()