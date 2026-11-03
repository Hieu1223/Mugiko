"""Word service for word deck module."""
from typing import Optional
from uuid import UUID

from mugiko.modules.core.word_deck.persistent.repository import DeckRepository, DeckWordRepository
from mugiko.modules.core.word_deck.persistent.dtos import DeckWordDTO, CreateDeckWordRequest, UpdateDeckWordRequest, PaginatedDeckWordsResponse
from mugiko.modules.core.word_deck.exceptions.word_deck_exceptions import DeckNotFoundError, DeckWordNotFoundError, DeckAccessDeniedError, DeckValidationError


class WordService:
    """Service for deck word operations."""
    
    def __init__(self, deck_repository: DeckRepository, word_repository: DeckWordRepository):
        self.deck_repository = deck_repository
        self.word_repository = word_repository

    async def add_word(self, deck_id: UUID, user_id: UUID, request: CreateDeckWordRequest) -> DeckWordDTO:
        """Add a word to a deck."""
        if not request.word or not request.word.strip():
            raise DeckValidationError("Word cannot be empty")
        if not request.meaning or not request.meaning.strip():
            raise DeckValidationError("Meaning cannot be empty")

        # Verify deck ownership
        deck = await self.deck_repository.get_by_id(deck_id)
        if not deck:
            raise DeckNotFoundError(str(deck_id))
        
        if deck.owner_id != user_id:
            raise DeckAccessDeniedError()

        word = await self.word_repository.create(deck_id, request.word.strip(), request.meaning.strip())
        return word

    async def get_word(self, word_id: UUID, user_id: UUID) -> DeckWordDTO:
        """Get a word by ID, verifying deck ownership."""
        word = await self.word_repository.get_by_id(word_id)
        if not word:
            raise DeckWordNotFoundError(str(word_id))

        # Verify deck ownership
        deck = await self.deck_repository.get_by_id(word.deck_id)
        if not deck or deck.owner_id != user_id:
            raise DeckAccessDeniedError()

        return word

    async def list_words(self, deck_id: UUID, user_id: UUID, page: int = 1, page_size: int = 50) -> PaginatedDeckWordsResponse:
        """List words in a deck."""
        # Verify deck ownership
        deck = await self.deck_repository.get_by_id(deck_id)
        if not deck:
            raise DeckNotFoundError(str(deck_id))
        
        if deck.owner_id != user_id:
            raise DeckAccessDeniedError()

        return await self.word_repository.list_by_deck(deck_id, page, page_size)

    async def update_word(self, word_id: UUID, user_id: UUID, request: UpdateDeckWordRequest) -> DeckWordDTO:
        """Update a word."""
        if not request.word or not request.word.strip():
            raise DeckValidationError("Word cannot be empty")
        if not request.meaning or not request.meaning.strip():
            raise DeckValidationError("Meaning cannot be empty")

        # Get word and verify ownership
        word = await self.word_repository.get_by_id(word_id)
        if not word:
            raise DeckWordNotFoundError(str(word_id))

        deck = await self.deck_repository.get_by_id(word.deck_id)
        if not deck or deck.owner_id != user_id:
            raise DeckAccessDeniedError()

        updated = await self.word_repository.update(word_id, request.word.strip(), request.meaning.strip())
        if not updated:
            raise DeckWordNotFoundError(str(word_id))
        
        return updated

    async def delete_word(self, word_id: UUID, user_id: UUID) -> bool:
        """Delete a word."""
        # Get word and verify ownership
        word = await self.word_repository.get_by_id(word_id)
        if not word:
            raise DeckWordNotFoundError(str(word_id))

        deck = await self.deck_repository.get_by_id(word.deck_id)
        if not deck or deck.owner_id != user_id:
            raise DeckAccessDeniedError()

        return await self.word_repository.delete(word_id)