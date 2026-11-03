"""Manga module API schemas."""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from mugiko.modules.media.manga.service.dtos import ProviderVisibility

# Provider schemas
class MangaProviderCreate(BaseModel):
    name: str
    base_url: str
    visibility: ProviderVisibility = ProviderVisibility.PRIVATE


class MangaProviderUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    visibility: Optional[ProviderVisibility] = None


class MangaProviderResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    base_url: str
    visibility: ProviderVisibility
    is_builtin: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Subscription schemas
class MangaSubscriptionResponse(BaseModel):
    user_id: UUID
    provider_id: UUID
    created_at: datetime
    provider: Optional[MangaProviderResponse] = None

    class Config:
        from_attributes = True


# History schemas
class MangaHistoryEntry(BaseModel):
    provider_id: UUID
    manga_id: str
    chapter_id: str
    page_index: int = 0
    title: str
    cover_url: Optional[str] = None


class MangaHistoryResponse(BaseModel):
    user_id: UUID
    provider_id: UUID
    manga_id: str
    chapter_id: str
    page_index: int
    title: str
    cover_url: Optional[str]
    last_read_at: datetime
    provider: Optional[MangaProviderResponse] = None

    class Config:
        from_attributes = True


class MangaHistoryListResponse(BaseModel):
    items: List[MangaHistoryResponse]
    page: int
    page_size: int
    total: int


# Settings schemas
class MangaUserSettingsResponse(BaseModel):
    user_id: UUID
    schema_version: int
    data: Dict[str, Any]
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MangaUserSettingsUpdate(BaseModel):
    schema_version: Optional[int] = None
    data: Optional[Dict[str, Any]] = None