"""Provider schemas."""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime

from mugiko.modules.media.subtitle.service.dtos import ProviderKind


class SubtitleProviderCreate(BaseModel):
    name: str
    kind: ProviderKind
    base_url: Optional[str] = None


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


class SubtitleProviderResponse(BaseModel):
    id: UUID
    name: str
    kind: ProviderKind
    base_url: Optional[str]
    is_active: bool
    last_synced_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    services: List[SubtitleProviderServiceResponse] = []

    class Config:
        from_attributes = True