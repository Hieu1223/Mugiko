"""API schemas for deck operations."""
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


class DeckCreateRequest(BaseModel):
    """Request to create a deck."""
    name: str = Field(..., min_length=1, max_length=100)


class DeckUpdateRequest(BaseModel):
    """Request to update a deck."""
    name: str = Field(..., min_length=1, max_length=100)


class DeckResponse(BaseModel):
    """Deck response."""
    id: UUID
    owner_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime


class PaginatedDecksResponse(BaseModel):
    """Paginated decks response."""
    decks: list[DeckResponse]
    total: int
    page: int
    page_size: int