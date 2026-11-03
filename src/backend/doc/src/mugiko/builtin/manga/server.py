"""Built-in manga provider implementation (server-side)."""
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mugiko.modules.media.manga.persistent.models import (
    BuiltinManga,
    BuiltinTag,
    BuiltinChapter,
    BuiltinPage,
    BuiltinImageTemplate,
    BuiltinMangaTag,
)
from mugiko.modules.media.manga.service.dtos import (
    BuiltinProviderInfo,
    BuiltinTagListResponse,
    BuiltinMangaListResponse,
    BuiltinMangaSummary,
    BuiltinMangaDetail,
    BuiltinChapterListResponse,
    BuiltinChapterSummary,
    BuiltinChapterDetail,
    BuiltinPageListResponse,
    BuiltinPageResponse,
    BuiltinTagResponse,
)
from mugiko.modules.media.manga.exceptions import MangaError
from fastapi import status
from mugiko.modules.media.manga.persistent.repository import MangaRepository


class BuiltinProvider:
    """Built-in manga provider implementation (server-side)."""

    def __init__(self, repo: MangaRepository, public_base_url: str):
        self.repo = repo
        self.public_base_url = public_base_url.rstrip("/")

    # Part 1.1: GET /info
    async def get_info(self) -> BuiltinProviderInfo:
        """Get provider metadata."""
        return BuiltinProviderInfo(
            name="Mugiko Built-in Manga Provider",
            description="Built-in manga provider for the Mugiko application",
            api_version="1",
        )

    # Part 1.2: GET /tags
    async def get_tags(
        self,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> BuiltinTagListResponse:
        """Get supported tags."""
        tags, _ = await self.repo.get_builtin_tags(category=category, page=page, page_size=page_size)
        return BuiltinTagListResponse(
            items=[BuiltinTagResponse.model_validate(t) for t in tags]
        )

    # Part 1.3: GET /manga
    async def search_manga(
        self,
        q: Optional[str] = None,
        tags: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort: Optional[str] = None,
    ) -> BuiltinMangaListResponse:
        """Search and list manga."""
        manga_list, total = await self.repo.search_builtin_manga(
            q=q,
            tags=tags,
            page=page,
            page_size=page_size,
            sort=sort,
        )

        items = []
        for manga in manga_list:
            # Build cover/thumbnail URLs
            cover_url = None
            thumbnail_url = None

            cover_template_id = manga.cover_template_id
            if cover_template_id:  # type: ignore
                template = await self.repo.get_image_template(cover_template_id)  # type: ignore
                if template:
                    cover_url = await self.repo.render_image_url(
                        template=template.template,  # type: ignore
                        manga=manga,
                        cover_vars=manga.cover_vars or {},  # type: ignore
                    )

            thumbnail_template_id = manga.thumbnail_template_id
            if thumbnail_template_id:  # type: ignore
                template = await self.repo.get_image_template(thumbnail_template_id)  # type: ignore
                if template:
                    thumbnail_url = await self.repo.render_image_url(
                        template=template.template,  # type: ignore
                        manga=manga,
                        cover_vars=manga.cover_vars or {},  # type: ignore
                    )
            elif cover_url:
                thumbnail_url = cover_url

            # Build tags
            tag_responses = [
                BuiltinTagResponse.model_validate(mt.tag)
                for mt in manga.tags
                if mt.tag is not None
            ]

            # Build latest chapters (newest 3)
            sorted_chapters = sorted(manga.chapters, key=lambda c: c.published_at, reverse=True)
            latest = [
                BuiltinChapterSummary(
                    id=c.id,
                    number=c.number,
                    published_at=c.published_at,
                )
                for c in sorted_chapters[:3]
            ]

            items.append(BuiltinMangaSummary(
                id=manga.id,  # type: ignore
                slug=manga.slug,  # type: ignore
                title=manga.title,  # type: ignore
                alternative_titles=manga.alternative_titles or [],  # type: ignore
                cover_url=cover_url,
                thumbnail_url=thumbnail_url,
                tags=tag_responses,
                score=float(manga.score),  # type: ignore
                views=manga.views,  # type: ignore
                latest_chapters=latest,
                updated_at=manga.updated_at,  # type: ignore
            ))

        return BuiltinMangaListResponse(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
        )

    # Part 1.4: GET /manga/{manga_id}
    async def get_manga(self, manga_id: UUID) -> BuiltinMangaDetail:
        """Get manga detail."""
        manga = await self.repo.get_builtin_manga(manga_id)
        if not manga:
            raise MangaError(
                detail="Manga not found",
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="MANGA_NOT_FOUND",
            )

        # Build cover/thumbnail URLs
        cover_url = None
        thumbnail_url = None

        cover_template_id = manga.cover_template_id
        if cover_template_id:  # type: ignore
            template = await self.repo.get_image_template(cover_template_id)  # type: ignore
            if template:
                cover_url = await self.repo.render_image_url(
                    template=template.template,  # type: ignore
                    manga=manga,
                    cover_vars=manga.cover_vars or {},  # type: ignore
                )

        thumbnail_template_id = manga.thumbnail_template_id
        if thumbnail_template_id:  # type: ignore
            template = await self.repo.get_image_template(thumbnail_template_id)  # type: ignore
            if template:
                thumbnail_url = await self.repo.render_image_url(
                    template=template.template,  # type: ignore
                    manga=manga,
                    cover_vars=manga.cover_vars or {},  # type: ignore
                )
        elif cover_url:
            thumbnail_url = cover_url

        # Build tags
        tag_responses = [
            BuiltinTagResponse.model_validate(mt.tag)
            for mt in manga.tags
            if mt.tag is not None
        ]

        # Build latest chapters (newest 3)
        sorted_chapters = sorted(manga.chapters, key=lambda c: c.published_at, reverse=True)
        latest = [
            BuiltinChapterSummary(
                id=c.id,  # type: ignore
                number=c.number,  # type: ignore
                published_at=c.published_at,  # type: ignore
            )
            for c in sorted_chapters[:3]
        ]

        return BuiltinMangaDetail(
            id=manga.id,  # type: ignore
            slug=manga.slug,  # type: ignore
            title=manga.title,  # type: ignore
            alternative_titles=manga.alternative_titles or [],  # type: ignore
            cover_url=cover_url,
            thumbnail_url=thumbnail_url,
            description=manga.description,  # type: ignore
            source_url=manga.source_url,  # type: ignore
            tags=tag_responses,
            score=float(manga.score),  # type: ignore
            views=manga.views,  # type: ignore
            created_at=manga.created_at,  # type: ignore
            updated_at=manga.updated_at,  # type: ignore
            latest_chapters=latest,
        )

    # Part 1.5: GET /manga/{manga_id}/chapters
    async def get_chapters(self, manga_id: UUID) -> BuiltinChapterListResponse:
        """Get chapter list for a manga."""
        chapters = await self.repo.get_builtin_chapters(manga_id)
        items = [
            BuiltinChapterSummary(
                id=c.id,
                number=c.number,
                published_at=c.published_at,
            )
            for c in chapters
        ]
        return BuiltinChapterListResponse(items=items)

    # Part 1.6: GET /chapters/{chapter_id}/pages
    async def get_pages(self, chapter_id: UUID) -> BuiltinPageListResponse:
        """Get pages for a chapter."""
        # Get chapter with manga eager loaded
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from mugiko.modules.media.manga.persistent.models import BuiltinChapter
        
        result = await self.repo.session.execute(
            select(BuiltinChapter)
            .options(selectinload(BuiltinChapter.manga))
            .where(BuiltinChapter.id == chapter_id)
        )
        chapter = result.scalar_one_or_none()
        
        if not chapter:
            raise MangaError(
                detail="Chapter not found",
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="CHAPTER_NOT_FOUND",
            )

        pages = await self.repo.get_builtin_pages(chapter_id)

        # Get image template
        template = None
        if chapter.image_template_id is not None:  # type: ignore
            template = await self.repo.get_image_template(chapter.image_template_id)  # type: ignore

        # Get uniform width/height from chapter image_vars or defaults
        width = chapter.image_vars.get("width", 800) if chapter.image_vars else 800  # type: ignore
        height = chapter.image_vars.get("height", 1200) if chapter.image_vars else 1200  # type: ignore

        page_responses = []
        for idx, page in enumerate(pages):
            urls = []
            if template:
                # Generate URL for this page
                url = await self.repo.render_image_url(
                    template=template.template,  # type: ignore
                    manga=chapter.manga,
                    chapter=chapter,
                    page=page,
                    page_idx=idx,
                    image_vars=chapter.image_vars,  # type: ignore
                )
                urls.append(url)

            page_responses.append(BuiltinPageResponse(
                index=idx,
                width=width,
                height=height,
                urls=urls,
            ))

        return BuiltinPageListResponse(
            width=width,
            height=height,
            pages=page_responses,
        )

    # Part 1.7: GET /manga/{manga_id}/chapters/{chapter_id}
    async def get_chapter(self, chapter_id: UUID) -> BuiltinChapterDetail:
        """Get chapter detail with pages."""
        chapter = await self.repo.get_builtin_chapter(chapter_id)
        if not chapter:
            raise MangaError(
                detail="Chapter not found",
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="CHAPTER_NOT_FOUND",
            )

        # Get pages
        pages_response = await self.get_pages(chapter_id)

        return BuiltinChapterDetail(
            id=chapter.id,  # type: ignore
            manga_id=chapter.manga_id,  # type: ignore
            number=chapter.number,  # type: ignore
            title=chapter.title,  # type: ignore
            published_at=chapter.published_at,  # type: ignore
            pages=pages_response.pages,
        )
