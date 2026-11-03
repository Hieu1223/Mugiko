"""Deck service for word deck module."""
from typing import Optional
from uuid import UUID

from mugiko.modules.core.word_deck.persistent.repository import DeckRepository
from mugiko.modules.core.word_deck.persistent.dtos import DeckDTO, CreateDeckRequest, UpdateDeckRequest, PaginatedDecksResponse
from mugiko.modules.core.word_deck.exceptions.word_deck_exceptions import DeckNotFoundError, DeckAccessDeniedError, DeckValidationError


class DeckService:
    """Service for deck operations."""
    
    def __init__(self, repository: DeckRepository):
        self.repository = repository

    async def create_deck(self, owner_id: UUID, request: CreateDeckRequest) -> DeckDTO:
        """Create a new deck."""
        if not request.name or not request.name.strip():
            raise DeckValidationError("Deck name cannot be empty")

        deck = await self.repository.create(owner_id, request.name.strip())
        return deck

    async def get_deck(self, deck_id: UUID, user_id: UUID) -> DeckDTO:
        """Get a deck by ID, verifying ownership."""
        deck = await self.repository.get_by_id(deck_id)
        if not deck:
            raise DeckNotFoundError(str(deck_id))

        if deck.owner_id != user_id:
            raise DeckAccessDeniedError()

        return deck

    async def list_decks(self, user_id: UUID, page: int = 1, page_size: int = 20) -> PaginatedDecksResponse:
        """List decks for a user."""
        return await self.repository.list_by_owner(user_id, page, page_size)

    async def update_deck(self, deck_id: UUID, user_id: UUID, request: UpdateDeckRequest) -> DeckDTO:
        """Update a deck."""
        if not request.name or not request.name.strip():
            raise DeckValidationError("Deck name cannot be empty")
        
        # Verify ownership first
        deck = await self.repository.get_by_id(deck_id)
        if not deck:
            raise DeckNotFoundError(str(deck_id))
        
        if deck.owner_id != user_id:
            raise DeckAccessDeniedError()

        updated = await self.repository.update(deck_id, request.name.strip())
        if not updated:
            raise DeckNotFoundError(str(deck_id))
        
        return updated

    async def delete_deck(self, deck_id: UUID, user_id: UUID) -> bool:
        """Delete a deck."""
        # Verify ownership first
        deck = await self.repository.get_by_id(deck_id)
        if not deck:
            raise DeckNotFoundError(str(deck_id))
        
        if deck.owner_id != user_id:
            raise DeckAccessDeniedError()

        return await self.repository.delete(deck_id)