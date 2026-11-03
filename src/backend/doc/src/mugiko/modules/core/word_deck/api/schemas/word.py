"""API schemas for word operations."""
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class DeckWordCreateRequest(BaseModel):
    """Request to create a deck word."""
    word: str = Field(..., min_length=1, max_length=255)
    meaning: str = Field(..., min_length=1)


class DeckWordUpdateRequest(BaseModel):
    """Request to update a deck word."""
    word: str = Field(..., min_length=1, max_length=255)
    meaning: str = Field(..., min_length=1)


class DeckWordResponse(BaseModel):
    """Deck word response."""
    id: UUID
    deck_id: UUID
    word: str
    meaning: str
    created_at: datetime
    updated_at: datetime


class PaginatedDeckWordsResponse(BaseModel):
    """Paginated deck words response."""
    words: list[DeckWordResponse]
    total: int
    page: int
    page_size: int