"""Web novel API schemas."""
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from enum import Enum


class SourceEnum(str, Enum):
    SYOSETSU = "syosetsu"


class WordToken(BaseModel):
    surface: str
    dictionary_form: str
    reading: str
    pos: str


class ParagraphResponse(BaseModel):
    id: UUID
    chapter_id: UUID
    idx: int
    text: str
    words: List[WordToken]

    class Config:
        from_attributes = True


class ChapterResponse(BaseModel):
    id: UUID
    novel_id: UUID
    idx: int
    title: Optional[str]
    created_at: datetime
    paragraphs: List[ParagraphResponse] = []

    class Config:
        from_attributes = True


class NovelResponse(BaseModel):
    id: UUID
    source: SourceEnum
    source_id: str
    url: str
    title: str
    author: Optional[str]
    synopsis: Optional[str]
    added_by: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class NovelWithChaptersResponse(NovelResponse):
    chapters: List[ChapterResponse] = []


class PreviewRequest(BaseModel):
    url: str


class PreviewResponse(BaseModel):
    source: SourceEnum
    source_id: str
    url: str
    title: str
    author: Optional[str]
    synopsis: Optional[str]
    chapter_count: int


class AddNovelRequest(BaseModel):
    url: str


class AddNovelResponse(BaseModel):
    novel: NovelResponse
    job_id: UUID


class PaginatedNovelsResponse(BaseModel):
    novels: List[NovelResponse]
    total: int
    page: int
    page_size: int