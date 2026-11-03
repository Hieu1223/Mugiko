"""Subtitle schemas."""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime


class SubtitleCreate(BaseModel):
    video_url: str
    provider_id: UUID
    service_key: str


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


class SubtitleResponse(BaseModel):
    id: UUID
    video_id: str
    video_url: str
    provider_id: UUID
    service_id: UUID
    created_by: UUID
    created_at: datetime
    segments: List[SubtitleSegmentResponse] = []

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