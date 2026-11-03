"""Web Novel API dependencies."""
from typing import AsyncGenerator
from mugiko.modules.media.web_novel.service.novel_service import NovelService
from mugiko.modules.media.web_novel.persistent.repository import NovelRepository, ChapterRepository, ParagraphRepository
from mugiko.common.persistent.session import async_session_maker


async def get_novel_service() -> AsyncGenerator[NovelService, None]:
    """Get novel service dependency."""
    async with async_session_maker() as session:
        novel_repo = NovelRepository(session)
        chapter_repo = ChapterRepository(session)
        paragraph_repo = ParagraphRepository(session)
        yield NovelService(novel_repo, chapter_repo, paragraph_repo)