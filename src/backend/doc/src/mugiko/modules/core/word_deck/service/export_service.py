"""Export service for word deck module."""
from uuid import UUID
from typing import TypeVar
from pydantic import BaseModel

from mugiko.modules.core.word_deck.service.export.base import ExportParams, ExportResultDTO
from mugiko.modules.core.word_deck.service.export.registry import registry
from mugiko.modules.core.word_deck.persistent.repository import DeckRepository, DeckWordRepository
from mugiko.modules.core.word_deck.persistent.dtos import DeckDTO, DeckWordDTO
from mugiko.modules.core.word_deck.exceptions.word_deck_exceptions import DeckNotFoundError, DeckAccessDeniedError


P = TypeVar("P", bound=BaseModel)


class ExportService:
    """Service for exporting decks."""
    
    def __init__(self, deck_repository: DeckRepository, word_repository: DeckWordRepository):
        self.deck_repository = deck_repository
        self.word_repository = word_repository

    async def export_deck(
        self,
        deck_id: UUID,
        user_id: UUID,
        format_key: str,
        params: P,
    ) -> ExportResultDTO:
        """Export a deck in the specified format."""
        # Get deck and verify ownership
        deck = await self.deck_repository.get_by_id(deck_id)
        if not deck:
            raise DeckNotFoundError(str(deck_id))

        if deck.owner_id != user_id:
            raise DeckAccessDeniedError()

        # Get all words for export
        words = await self.word_repository.get_all_by_deck(deck_id)

        # Get exporter
        exporter = registry.get_exporter(format_key)
        if not exporter:
            raise ValueError(f"Unknown export format: {format_key}")

        # Export
        return await exporter.export(deck, words, params)