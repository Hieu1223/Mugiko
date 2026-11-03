"""Export base classes for word deck module."""
from typing import Protocol, TypeVar, Generic
from dataclasses import dataclass
from pydantic import BaseModel

from mugiko.modules.core.word_deck.persistent.dtos import DeckDTO, DeckWordDTO


P = TypeVar("P", bound=BaseModel)


@dataclass
class ExportResultDTO:
    """Result of an export operation."""
    content: bytes
    media_type: str
    filename: str


class ExportParams(BaseModel):
    """Base class for export parameters."""
    pass


class DeckExporter(Protocol[P]):
    """Protocol for deck exporters."""
    format_key: str

    async def export(self, deck: DeckDTO, words: list[DeckWordDTO], params: P) -> ExportResultDTO:
        """Export a deck and its words."""
        ...