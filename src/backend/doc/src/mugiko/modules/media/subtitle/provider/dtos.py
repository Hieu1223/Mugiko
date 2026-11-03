"""Provider DTOs for subtitle module."""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime


class SubtitleWordDTO(BaseModel):
    text: str
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    hiragana: Optional[str] = None


class SubtitleSegmentProviderDTO(BaseModel):
    idx: int
    start_ms: int
    end_ms: int
    words: Optional[List[SubtitleWordDTO]] = None


class SubtitleResultDTO(BaseModel):
    video_id: str
    video_url: str
    segments: List[SubtitleSegmentProviderDTO]


class ProviderServiceDTO(BaseModel):
    service_key: str
    name: str
    options: Optional[Dict[str, Any]] = None


class ProviderSyncDTO(BaseModel):
    provider_name: str
    provider_kind: str  # "remote" or "youtube"
    services: List[ProviderServiceDTO]


class RemoteProviderConfigDTO(BaseModel):
    base_url: str
    # No auth for now per plan


class YouTubeProviderConfigDTO(BaseModel):
    # No config needed for YouTube provider
    pass