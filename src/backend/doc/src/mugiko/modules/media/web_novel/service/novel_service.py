"""Novel service for web novel module."""
from typing import Optional, List
from uuid import UUID

from mugiko.modules.media.web_novel.persistent.repository import NovelRepository, ChapterRepository, ParagraphRepository
from mugiko.modules.media.web_novel.persistent.dtos import (
    NovelDTO, ChapterDTO, ParagraphDTO, NovelWithChaptersDTO,
    CreateNovelRequest, PreviewResponse, PaginatedNovelsResponse, SourceEnum
)
from mugiko.modules.media.web_novel.provider.syosetsu import SyosetsuProvider
from mugiko.modules.media.web_novel.exceptions.web_novel_exceptions import (
    NovelNotFoundError, NovelAlreadyExistsError, InvalidUrlError, ProviderError
)
from mugiko.modules.core.job.persistent.models import JobType
from mugiko.modules.core.job.persistent.repository import JobRepository
from mugiko.modules.media.web_novel.service.sync_service import run_sync_background
from mugiko.common.persistent.session import async_session_maker
import asyncio


class NovelService:
    """Service for novel operations."""

    def __init__(self, novel_repo: NovelRepository, chapter_repo: ChapterRepository, paragraph_repo: ParagraphRepository):
        self.novel_repo = novel_repo
        self.chapter_repo = chapter_repo
        self.paragraph_repo = paragraph_repo

    async def preview(self, url: str) -> PreviewResponse:
        """Preview a novel from URL without saving."""
        novel_code = SyosetsuProvider().validate_url(url)
        if not novel_code:
            raise InvalidUrlError("Invalid Syosetsu URL format")

        async with SyosetsuProvider() as provider:
            try:
                metadata = await provider.fetch_metadata(novel_code)
            except Exception as e:
                raise ProviderError(f"Failed to fetch novel metadata: {str(e)}")

        return PreviewResponse(
            source=SourceEnum.SYOSETSU,
            source_id=metadata.source_id,
            url=url,
            title=metadata.title,
            author=metadata.author,
            synopsis=metadata.synopsis,
            chapter_count=metadata.chapter_count,
        )

    async def add_novel(self, user_id: UUID, url: str) -> tuple:
        """Add a novel and create initial sync job."""
        novel_code = SyosetsuProvider().validate_url(url)
        if not novel_code:
            raise InvalidUrlError("Invalid Syosetsu URL format")

        # Check if already exists
        async with async_session_maker() as session:
            novel_repo = NovelRepository(session)
            existing = await novel_repo.get_by_source_id(
                source=SourceEnum.SYOSETSU,
                source_id=novel_code
            )
            if existing:
                # Return existing novel with its latest job
                job_repo = JobRepository(session)
                jobs = await job_repo.get_jobs_by_ref("novel", existing.id)
                job_id = jobs[0].job_id if jobs else None
                return self._to_dto(existing), job_id

        # Fetch metadata
        async with SyosetsuProvider() as provider:
            try:
                metadata = await provider.fetch_metadata(novel_code)
            except Exception as e:
                raise ProviderError(f"Failed to fetch novel metadata: {str(e)}")

        # Create novel and job in transaction
        async with async_session_maker() as session:
            novel_repo = NovelRepository(session)
            job_repo = JobRepository(session)

            novel = await novel_repo.create(CreateNovelRequest(
                source=SourceEnum.SYOSETSU,
                source_id=novel_code,
                url=url,
                title=metadata.title,
                author=metadata.author,
                synopsis=metadata.synopsis,
                added_by=user_id,
            ))

            job = await job_repo.create_job(
                job_type=JobType.NOVEL_SYNC,
                ref_type="novel",
                ref_id=novel.id,
            )

            await session.commit()
            await session.refresh(novel)
            await session.refresh(job)

            # Start background sync
            asyncio.create_task(run_sync_background(novel.id, job.job_id))

            return self._to_dto(novel), job.job_id

    async def get_novel(self, novel_id: UUID) -> NovelWithChaptersDTO:
        """Get novel with chapters (without paragraphs)."""
        novel = await self.novel_repo.get_by_id(novel_id)
        if not novel:
            raise NovelNotFoundError(str(novel_id))

        chapters = await self.chapter_repo.list_by_novel(novel_id)

        return NovelWithChaptersDTO(
            id=novel.id,
            source=novel.source,
            source_id=novel.source_id,
            url=novel.url,
            title=novel.title,
            author=novel.author,
            synopsis=novel.synopsis,
            added_by=novel.added_by,
            created_at=novel.created_at,
            chapters=[
                ChapterDTO(
                    id=c.id,
                    novel_id=c.novel_id,
                    idx=c.idx,
                    title=c.title,
                    created_at=c.created_at,
                    paragraphs=[],
                )
                for c in chapters
            ],
        )

    async def get_chapter(self, chapter_id: UUID) -> ChapterDTO:
        """Get chapter with paragraphs and words."""
        chapter = await self.chapter_repo.get_by_id(chapter_id)
        if not chapter:
            raise NovelNotFoundError(str(chapter_id))

        paragraphs = await self.paragraph_repo.get_by_chapter(chapter_id)

        return ChapterDTO(
            id=chapter.id,
            novel_id=chapter.novel_id,
            idx=chapter.idx,
            title=chapter.title,
            created_at=chapter.created_at,
            paragraphs=[
                ParagraphDTO(
                    id=p.id,
                    chapter_id=p.chapter_id,
                    idx=p.idx,
                    text=p.text,
                    words=p.words,
                )
                for p in paragraphs
            ],
        )

    async def get_chapter_paginated(self, chapter_id: UUID, limit: int = 50, offset: int = 0) -> ChapterDTO:
        """Get chapter with paginated paragraphs."""
        chapter = await self.chapter_repo.get_by_id(chapter_id)
        if not chapter:
            raise NovelNotFoundError(str(chapter_id))

        paragraphs = await self.paragraph_repo.get_by_chapter_paginated(chapter_id, limit, offset)

        return ChapterDTO(
            id=chapter.id,
            novel_id=chapter.novel_id,
            idx=chapter.idx,
            title=chapter.title,
            created_at=chapter.created_at,
            paragraphs=[
                ParagraphDTO(
                    id=p.id,
                    chapter_id=p.chapter_id,
                    idx=p.idx,
                    text=p.text,
                    words=p.words,
                )
                for p in paragraphs
            ],
        )

    async def list_novels_by_user(self, user_id: UUID, page: int = 1, page_size: int = 20) -> PaginatedNovelsResponse:
        """List novels added by user."""
        return await self.novel_repo.list_by_user(user_id, page, page_size)

    async def list_all_novels(self, page: int = 1, page_size: int = 20) -> PaginatedNovelsResponse:
        """List all novels (catalog)."""
        return await self.novel_repo.list_all(page, page_size)

    def _to_dto(self, novel) -> NovelDTO:
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
