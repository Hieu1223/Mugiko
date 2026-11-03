"""Manga history routes."""
from fastapi import APIRouter, Depends, status, Query
from uuid import UUID
from typing import List

from mugiko.modules.media.manga.api.schemas import (
    MangaHistoryEntry as APIMangaHistoryEntry,
    MangaHistoryResponse as APIMangaHistoryResponse,
    MangaHistoryListResponse,
)
from mugiko.modules.media.manga.api.dependencies import get_history_service
from mugiko.modules.media.manga.service.history_service import HistoryService
from mugiko.modules.media.manga.service.dtos import (
    MangaHistoryEntry as ServiceMangaHistoryEntry,
    MangaHistoryResponse as ServiceMangaHistoryResponse,
)
from mugiko.modules.core.user_management.api.dependencies import require_user
from mugiko.modules.core.user_management.service.dtos import AuthContext

router = APIRouter(prefix="/manga", tags=["manga"])


@router.put(
    "/history",
    response_model=APIMangaHistoryResponse,
)
async def upsert_history(
    data: APIMangaHistoryEntry,
    service: HistoryService = Depends(get_history_service),
    auth: AuthContext = Depends(require_user),
):
    """Upsert reading history entry."""
    service_data = ServiceMangaHistoryEntry(
        provider_id=data.provider_id,
        manga_id=data.manga_id,
        chapter_id=data.chapter_id,
        page_index=data.page_index,
        title=data.title,
        cover_url=data.cover_url,
    )
    result = await service.upsert_history(service_data, auth)
    return APIMangaHistoryResponse.model_validate(result)


@router.get(
    "/history",
    response_model=MangaHistoryListResponse,
)
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: HistoryService = Depends(get_history_service),
    auth: AuthContext = Depends(require_user),
):
    """Get reading history."""
    items, total = await service.get_user_history(auth.user_id, page, page_size)
    api_items = [APIMangaHistoryResponse.model_validate(item) for item in items]
    return MangaHistoryListResponse(
        items=api_items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.delete(
    "/history/{provider_id}/{manga_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_history(
    provider_id: UUID,
    manga_id: str,
    service: HistoryService = Depends(get_history_service),
    auth: AuthContext = Depends(require_user),
):
    """Delete reading history entry."""
    await service.delete_history(provider_id, manga_id, auth)