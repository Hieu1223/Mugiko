"""Repository for word deck module."""
from typing import Optional
from uuid import UUID
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mugiko.modules.core.word_deck.persistent.models import Deck, DeckWord
from mugiko.modules.core.word_deck.persistent.dtos import DeckDTO, DeckWordDTO, PaginatedDecksResponse, PaginatedDeckWordsResponse


class DeckRepository:
    """Repository for deck operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, owner_id: UUID, name: str) -> DeckDTO:
        """Create a new deck."""
        deck = Deck(owner_id=owner_id, name=name)
        self.session.add(deck)
        await self.session.flush()
        await self.session.refresh(deck)
        return self._to_dto(deck)

    async def get_by_id(self, deck_id: UUID) -> Optional[DeckDTO]:
        """Get deck by ID."""
        stmt = select(Deck).where(Deck.id == deck_id)
        result = await self.session.execute(stmt)
        deck = result.scalar_one_or_none()
        if deck:
            return self._to_dto(deck)
        return None

    async def get_by_id_with_words(self, deck_id: UUID) -> Optional[Deck]:
        """Get deck by ID with words loaded."""
        stmt = select(Deck).options(selectinload(Deck.words)).where(Deck.id == deck_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_owner(self, owner_id: UUID, page: int = 1, page_size: int = 20) -> PaginatedDecksResponse:
        """List decks by owner with pagination."""
        # Count total
        count_stmt = select(func.count(Deck.id)).where(Deck.owner_id == owner_id)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get paginated results
        stmt = (
            select(Deck)
            .where(Deck.owner_id == owner_id)
            .order_by(Deck.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        decks = result.scalars().all()

        return PaginatedDecksResponse(
            decks=[self._to_dto(d) for d in decks],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update(self, deck_id: UUID, name: str) -> Optional[DeckDTO]:
        """Update deck name."""
        stmt = select(Deck).where(Deck.id == deck_id)
        result = await self.session.execute(stmt)
        deck = result.scalar_one_or_none()
        if deck:
            deck.name = name
            await self.session.flush()
            await self.session.refresh(deck)
            return self._to_dto(deck)
        return None

    async def delete(self, deck_id: UUID) -> bool:
        """Delete a deck (cascades to words)."""
        stmt = delete(Deck).where(Deck.id == deck_id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    def _to_dto(self, deck: Deck) -> DeckDTO:
        """Convert model to DTO."""
        return DeckDTO(
            id=deck.id,
            owner_id=deck.owner_id,
            name=deck.name,
            created_at=deck.created_at,
            updated_at=deck.updated_at,
        )


class DeckWordRepository:
    """Repository for deck word operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, deck_id: UUID, word: str, meaning: str) -> DeckWordDTO:
        """Create a new deck word."""
        deck_word = DeckWord(deck_id=deck_id, word=word, meaning=meaning)
        self.session.add(deck_word)
        await self.session.flush()
        await self.session.refresh(deck_word)
        return self._to_dto(deck_word)

    async def get_by_id(self, word_id: UUID) -> Optional[DeckWordDTO]:
        """Get deck word by ID."""
        stmt = select(DeckWord).where(DeckWord.id == word_id)
        result = await self.session.execute(stmt)
        deck_word = result.scalar_one_or_none()
        if deck_word:
            return self._to_dto(deck_word)
        return None

    async def list_by_deck(self, deck_id: UUID, page: int = 1, page_size: int = 50) -> PaginatedDeckWordsResponse:
        """List words in a deck with pagination."""
        # Count total
        count_stmt = select(func.count(DeckWord.id)).where(DeckWord.deck_id == deck_id)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        # Get paginated results
        stmt = (
            select(DeckWord)
            .where(DeckWord.deck_id == deck_id)
            .order_by(DeckWord.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        words = result.scalars().all()

        return PaginatedDeckWordsResponse(
            words=[self._to_dto(w) for w in words],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update(self, word_id: UUID, word: str, meaning: str) -> Optional[DeckWordDTO]:
        """Update a deck word."""
        stmt = select(DeckWord).where(DeckWord.id == word_id)
        result = await self.session.execute(stmt)
        deck_word = result.scalar_one_or_none()
        if deck_word:
            deck_word.word = word
            deck_word.meaning = meaning
            await self.session.flush()
            await self.session.refresh(deck_word)
            return self._to_dto(deck_word)
        return None

    async def delete(self, word_id: UUID) -> bool:
        """Delete a deck word."""
        stmt = delete(DeckWord).where(DeckWord.id == word_id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def get_all_by_deck(self, deck_id: UUID) -> list[DeckWordDTO]:
        """Get all words in a deck (for export)."""
        stmt = select(DeckWord).where(DeckWord.deck_id == deck_id).order_by(DeckWord.created_at.asc())
        result = await self.session.execute(stmt)
        words = result.scalars().all()
        return [self._to_dto(w) for w in words]

    def _to_dto(self, deck_word: DeckWord) -> DeckWordDTO:
        """Convert model to DTO."""
        return DeckWordDTO(
            id=deck_word.id,
            deck_id=deck_word.deck_id,
            word=deck_word.word,
            meaning=deck_word.meaning,
            created_at=deck_word.created_at,
            updated_at=deck_word.updated_at,
        )