"""API routes for novel operations."""
from fastapi import APIRouter, Depends, Query, status
from uuid import UUID
from typing import AsyncGenerator

from mugiko.modules.media.web_novel.api.schemas.novel import (
    PreviewRequest,
    PreviewResponse,
    AddNovelRequest,
    AddNovelResponse,
    NovelResponse,
    NovelWithChaptersResponse,
    ChapterResponse,
    PaginatedNovelsResponse,
)
from mugiko.modules.media.web_novel.api.dependencies import get_novel_service
from mugiko.modules.media.web_novel.service.novel_service import NovelService
from mugiko.modules.core.user_management.api.dependencies import require_user
from mugiko.modules.core.user_management.service.dtos import AuthContext


router = APIRouter(prefix="/novels", tags=["web_novel"])


@router.post(
    "/preview",
    response_model=PreviewResponse,
    status_code=status.HTTP_200_OK,
)
async def preview_novel(
    request: PreviewRequest,
    auth_context: AuthContext = Depends(require_user),
    novel_service: NovelService = Depends(get_novel_service),
):
    """Preview a novel from Syosetsu URL."""
    return await novel_service.preview(request.url)


@router.post(
    "",
    response_model=AddNovelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_novel(
    request: AddNovelRequest,
    auth_context: AuthContext = Depends(require_user),
    novel_service: NovelService = Depends(get_novel_service),
):
    """Add a novel and trigger initial sync."""
    novel, job_id = await novel_service.add_novel(auth_context.user_id, request.url)
    return AddNovelResponse(novel=novel, job_id=job_id)


@router.get(
    "",
    response_model=PaginatedNovelsResponse,
)
async def list_novels(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    mine: bool = Query(False, description="Filter to current user's novels"),
    auth_context: AuthContext = Depends(require_user),
    novel_service: NovelService = Depends(get_novel_service),
):
    """List novels (all or current user's)."""
    if mine:
        return await novel_service.list_novels_by_user(auth_context.user_id, page, page_size)
    return await novel_service.list_all_novels(page, page_size)


@router.get(
    "/{novel_id}",
    response_model=NovelWithChaptersResponse,
)
async def get_novel(
    novel_id: UUID,
    auth_context: AuthContext = Depends(require_user),
    novel_service: NovelService = Depends(get_novel_service),
):
    """Get novel with chapter list."""
    return await novel_service.get_novel(novel_id)


@router.get(
    "/{novel_id}/chapters/{chapter_id}",
    response_model=ChapterResponse,
)
async def get_chapter(
    novel_id: UUID,
    chapter_id: UUID,
    auth_context: AuthContext = Depends(require_user),
    novel_service: NovelService = Depends(get_novel_service),
):
    """Get chapter with paragraphs and tokenized words."""
    return await novel_service.get_chapter(chapter_id)


@router.get(
    "/{novel_id}/chapters/{chapter_id}/paginated",
    response_model=ChapterResponse,
)
async def get_chapter_paginated(
    novel_id: UUID,
    chapter_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    auth_context: AuthContext = Depends(require_user),
    novel_service: NovelService = Depends(get_novel_service),
):
    """Get chapter with paginated paragraphs."""
    return await novel_service.get_chapter_paginated(chapter_id, limit, offset)