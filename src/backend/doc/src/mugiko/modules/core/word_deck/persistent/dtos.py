"""DTOs for word deck module."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class DeckDTO:
    """Deck data transfer object."""
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime


@dataclass
class DeckWordDTO:
    """Deck word data transfer object."""
    id: uuid.UUID
    deck_id: uuid.UUID
    word: str
    meaning: str
    created_at: datetime
    updated_at: datetime


@dataclass
class CreateDeckRequest:
    """Request to create a deck."""
    name: str


@dataclass
class UpdateDeckRequest:
    """Request to update a deck."""
    name: str


@dataclass
class CreateDeckWordRequest:
    """Request to create a deck word."""
    word: str
    meaning: str


@dataclass
class UpdateDeckWordRequest:
    """Request to update a deck word."""
    word: str
    meaning: str


@dataclass
class PaginatedDecksResponse:
    """Paginated decks response."""
    decks: list[DeckDTO]
    total: int
    page: int
    page_size: int


@dataclass
class PaginatedDeckWordsResponse:
    """Paginated deck words response."""
    words: list[DeckWordDTO]
    total: int
    page: int
    page_size: int