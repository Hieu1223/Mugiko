"""Built-in provider schemas (Part 1 interface)."""
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime


class BuiltinProviderInfo(BaseModel):
    name: str
    description: str
    api_version: str


class BuiltinTagResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    category: str

    class Config:
        from_attributes = True


class BuiltinTagListResponse(BaseModel):
    items: List[BuiltinTagResponse]


class BuiltinChapterSummary(BaseModel):
    id: UUID
    number: str
    published_at: datetime


class BuiltinMangaSummary(BaseModel):
    id: UUID
    slug: str
    title: str
    alternative_titles: List[str] = []
    cover_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    tags: List[BuiltinTagResponse] = []
    score: float
    views: int
    latest_chapters: List[BuiltinChapterSummary] = []
    updated_at: datetime


class BuiltinMangaListResponse(BaseModel):
    items: List[BuiltinMangaSummary]
    page: int
    page_size: int
    total: int


class BuiltinMangaDetail(BaseModel):
    id: UUID
    slug: str
    title: str
    alternative_titles: List[str] = []
    cover_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    tags: List[BuiltinTagResponse] = []
    score: float
    views: int
    created_at: datetime
    updated_at: datetime
    latest_chapters: List[BuiltinChapterSummary] = []


class BuiltinChapterDetail(BaseModel):
    id: UUID
    manga_id: UUID
    number: str
    title: Optional[str] = None
    published_at: datetime
    pages: List["BuiltinPageResponse"] = []


class BuiltinPageResponse(BaseModel):
    index: int
    width: int
    height: int
    urls: List[str]


class BuiltinChapterListResponse(BaseModel):
    items: List[BuiltinChapterSummary]


class BuiltinPageListResponse(BaseModel):
    width: int
    height: int
    pages: List[BuiltinPageResponse]


BuiltinChapterDetail.model_rebuild()