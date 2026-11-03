"""Manga module history service."""
from typing import List
from uuid import UUID

from mugiko.modules.media.manga.service.dtos import (
    MangaHistoryEntry,
    MangaHistoryResponse,
    MangaProviderResponse,
)
from mugiko.modules.media.manga.persistent.repository import MangaRepository
from mugiko.modules.media.manga.exceptions import HistoryNotFoundError, ForbiddenError
from mugiko.modules.core.user_management.service.dtos import AuthContext, Role


class HistoryService:
    """Service for managing reading history."""

    def __init__(self, repo: MangaRepository):
        self.repo = repo

    async def upsert_history(
        self,
        data: MangaHistoryEntry,
        auth: AuthContext,
    ) -> MangaHistoryResponse:
        """Upsert reading history entry."""
        history = await self.repo.upsert_history(auth.user_id, data.model_dump())

        provider = await self.repo.get_provider(data.provider_id)
        return MangaHistoryResponse(
            user_id=history.user_id,
            provider_id=history.provider_id,
            manga_id=history.manga_id,
            chapter_id=history.chapter_id,
            page_index=history.page_index,
            title=history.title,
            cover_url=history.cover_url,
            last_read_at=history.last_read_at,
            provider=MangaProviderResponse.model_validate(provider) if provider else None,
        )

    async def get_user_history(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[MangaHistoryResponse], int]:
        """Get user's reading history."""
        history_list, total = await self.repo.get_user_history(user_id, page, page_size)

        items = []
        for h in history_list:
            provider = None
            if h.provider:
                provider = MangaProviderResponse.model_validate(h.provider)

            items.append(MangaHistoryResponse(
                user_id=h.user_id,
                provider_id=h.provider_id,
                manga_id=h.manga_id,
                chapter_id=h.chapter_id,
                page_index=h.page_index,
                title=h.title,
                cover_url=h.cover_url,
                last_read_at=h.last_read_at,
                provider=provider,
            ))

        return items, total

    async def delete_history(
        self,
        provider_id: UUID,
        manga_id: str,
        auth: AuthContext,
    ) -> bool:
        """Delete reading history entry."""
        return await self.repo.delete_history(auth.user_id, provider_id, manga_id)