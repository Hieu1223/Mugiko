"""Word Deck API dependencies."""
from typing import AsyncGenerator
from mugiko.modules.core.word_deck.service.deck_service import DeckService
from mugiko.modules.core.word_deck.service.word_service import WordService
from mugiko.modules.core.word_deck.service.export_service import ExportService
from mugiko.modules.core.word_deck.persistent.repository import DeckRepository, DeckWordRepository
from mugiko.common.persistent.session import get_session_cm, async_session_maker


async def get_deck_service() -> AsyncGenerator[DeckService, None]:
    """Get deck service dependency."""
    async with get_session_cm() as session:
        repo = DeckRepository(session)
        yield DeckService(repo)


async def get_word_service() -> AsyncGenerator[WordService, None]:
    """Get word service dependency."""
    async with get_session_cm() as session:
        deck_repo = DeckRepository(session)
        word_repo = DeckWordRepository(session)
        yield WordService(deck_repo, word_repo)


async def get_export_service() -> AsyncGenerator[ExportService, None]:
    """Get export service dependency."""
    async with get_session_cm() as session:
        deck_repo = DeckRepository(session)
        word_repo = DeckWordRepository(session)
        yield ExportService(deck_repo, word_repo)