"""Web novel module repository."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from mugiko.modules.media.web_novel.persistent.models import Novel, Chapter, Paragraph, SourceEnum
from mugiko.modules.media.web_novel.persistent.dtos import NovelDTO, ChapterDTO, ParagraphDTO, CreateNovelRequest, PaginatedNovelsResponse


class NovelRepository:
    """Repository for web novel module data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_source_id(self, source: SourceEnum, source_id: str) -> Optional[Novel]:
        """Get novel by source and source_id."""
        result = await self.session.execute(
            select(Novel).where(
                Novel.source == source,
                Novel.source_id == source_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, novel_id: UUID) -> Optional[Novel]:
        """Get novel by ID."""
        result = await self.session.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        return result.scalar_one_or_none()

    async def get_with_chapters(self, novel_id: UUID) -> Optional[Novel]:
        """Get novel with chapters and paragraphs."""
        result = await self.session.execute(
            select(Novel).where(Novel.id == novel_id)
        )
        return result.scalar_one_or_none()

    async def create(self, request: CreateNovelRequest) -> Novel:
        """Create a new novel."""
        novel = Novel(
            source=request.source,
            source_id=request.source_id,
            url=request.url,
            title=request.title,
            author=request.author,
            synopsis=request.synopsis,
            added_by=request.added_by,
        )
        self.session.add(novel)
        await self.session.flush()
        return novel

    async def list_by_user(self, user_id: UUID, page: int = 1, page_size: int = 20) -> PaginatedNovelsResponse:
        """List novels by user with pagination."""
        offset = (page - 1) * page_size
        
        count_result = await self.session.execute(
            select(func.count(Novel.id)).where(Novel.added_by == user_id)
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(Novel)
            .where(Novel.added_by == user_id)
            .order_by(Novel.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        novels = list(result.scalars().all())

        return PaginatedNovelsResponse(
            novels=[self._to_dto(n) for n in novels],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_all(self, page: int = 1, page_size: int = 20) -> PaginatedNovelsResponse:
        """List all novels with pagination (for catalog)."""
        offset = (page - 1) * page_size
        
        count_result = await self.session.execute(
            select(func.count(Novel.id))
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(Novel)
            .order_by(Novel.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        novels = list(result.scalars().all())

        return PaginatedNovelsResponse(
            novels=[self._to_dto(n) for n in novels],
            total=total,
            page=page,
            page_size=page_size,
        )

    def _to_dto(self, novel: Novel) -> NovelDTO:
        return NovelDTO(
            id=novel.id,
            source=novel.source,
            source_id=novel.source_id,
            url=novel.url,
            title=novel.title,
            author=novel.author,
            synopsis=novel.synopsis,
            added_by=novel.added_by,
            created_at=novel.created_at,
        )


class ChapterRepository:
    """Repository for chapter data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, chapter_id: UUID) -> Optional[Chapter]:
        """Get chapter by ID with paragraphs."""
        result = await self.session.execute(
            select(Chapter).where(Chapter.id == chapter_id)
        )
        return result.scalar_one_or_none()

    async def get_by_novel_and_idx(self, novel_id: UUID, idx: int) -> Optional[Chapter]:
        """Get chapter by novel and index."""
        result = await self.session.execute(
            select(Chapter).where(
                Chapter.novel_id == novel_id,
                Chapter.idx == idx
            )
        )
        return result.scalar_one_or_none()

    async def create(self, novel_id: UUID, idx: int, title: Optional[str]) -> Chapter:
        """Create a new chapter."""
        chapter = Chapter(
            novel_id=novel_id,
            idx=idx,
            title=title,
        )
        self.session.add(chapter)
        await self.session.flush()
        return chapter

    async def list_by_novel(self, novel_id: UUID) -> List[Chapter]:
        """List all chapters for a novel in order."""
        result = await self.session.execute(
            select(Chapter)
            .where(Chapter.novel_id == novel_id)
            .order_by(Chapter.idx)
        )
        return list(result.scalars().all())


class ParagraphRepository:
    """Repository for paragraph data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_batch(self, chapter_id: UUID, paragraphs: List[dict]) -> List[Paragraph]:
        """Create multiple paragraphs for a chapter."""
        created = []
        for p in paragraphs:
            paragraph = Paragraph(
                chapter_id=chapter_id,
                idx=p['idx'],
                text=p['text'],
                words=p['words'],
            )
            self.session.add(paragraph)
            created.append(paragraph)
        await self.session.flush()
        return created

    async def get_by_chapter(self, chapter_id: UUID) -> List[Paragraph]:
        """Get all paragraphs for a chapter in order."""
        result = await self.session.execute(
            select(Paragraph)
            .where(Paragraph.chapter_id == chapter_id)
            .order_by(Paragraph.idx)
        )
        return list(result.scalars().all())

    async def get_by_chapter_paginated(self, chapter_id: UUID, limit: int = 50, offset: int = 0) -> List[Paragraph]:
        """Get paragraphs for a chapter with pagination."""
        result = await self.session.execute(
            select(Paragraph)
            .where(Paragraph.chapter_id == chapter_id)
            .order_by(Paragraph.idx)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_chapter(self, chapter_id: UUID) -> int:
        """Count total paragraphs in a chapter."""
        result = await self.session.execute(
            select(func.count(Paragraph.id)).where(Paragraph.chapter_id == chapter_id)
        )
        return result.scalar_one()