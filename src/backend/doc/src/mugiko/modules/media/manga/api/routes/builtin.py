"""Manga built-in provider routes (public API for clients)."""
from fastapi import APIRouter, Depends, Query
from uuid import UUID
from typing import Optional, List

from mugiko.builtin.manga.schemas import (
    BuiltinProviderInfo,
    BuiltinTagListResponse,
    BuiltinMangaListResponse,
    BuiltinMangaDetail,
    BuiltinChapterListResponse,
    BuiltinChapterDetail,
    BuiltinPageListResponse,
)
from mugiko.modules.media.manga.api.dependencies import get_builtin_provider
from mugiko.builtin.manga import BuiltinProvider

router = APIRouter(prefix="/builtin-provider", tags=["manga-builtin"])


@router.get(
    "/info",
    response_model=BuiltinProviderInfo,
)
async def get_info(
    provider: BuiltinProvider = Depends(get_builtin_provider),
):
    """Get built-in provider info."""
    return await provider.get_info()


@router.get(
    "/tags",
    response_model=BuiltinTagListResponse,
)
async def get_tags(
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    provider: BuiltinProvider = Depends(get_builtin_provider),
):
    """Get supported tags."""
    return await provider.get_tags(category=category, page=page, page_size=page_size)


@router.get(
    "/chapters",
    response_model=BuiltinChapterListResponse,
)
async def get_chapters(
    manga_id: UUID = Query(...),
    provider: BuiltinProvider = Depends(get_builtin_provider),
):
    """Get chapter list for a manga."""
    return await provider.get_chapters(manga_id)


@router.get(
    "/chapters/{chapter_id}",
    response_model=BuiltinChapterDetail,
)
async def get_chapter(
    chapter_id: UUID,
    provider: BuiltinProvider = Depends(get_builtin_provider),
):
    """Get chapter detail with pages."""
    return await provider.get_chapter(chapter_id)


@router.get(
    "/chapters/{chapter_id}/pages",
    response_model=BuiltinPageListResponse,
)
async def get_pages(
    chapter_id: UUID,
    provider: BuiltinProvider = Depends(get_builtin_provider),
):
    """Get pages for a chapter."""
    return await provider.get_pages(chapter_id)


@router.get(
    "/manga",
    response_model=BuiltinMangaListResponse,
)
async def search_manga(
    q: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: Optional[str] = Query(None),
    provider: BuiltinProvider = Depends(get_builtin_provider),
):
    """Search and list manga."""
    return await provider.search_manga(q=q, tags=tags, page=page, page_size=page_size, sort=sort)


@router.get(
    "/manga/{manga_id}",
    response_model=BuiltinMangaDetail,
)
async def get_manga(
    manga_id: UUID,
    provider: BuiltinProvider = Depends(get_builtin_provider),
):
    """Get manga detail."""
    return await provider.get_manga(manga_id)