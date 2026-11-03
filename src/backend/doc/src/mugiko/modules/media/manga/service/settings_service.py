"""Manga module settings service."""
from typing import Optional
from uuid import UUID

from mugiko.modules.media.manga.service.dtos import (
    MangaUserSettingsResponse,
    MangaUserSettingsUpdate,
)
from mugiko.modules.media.manga.persistent.repository import MangaRepository


class SettingsService:
    """Service for managing user settings."""

    def __init__(self, repo: MangaRepository):
        self.repo = repo

    async def get_settings(self, user_id: UUID) -> MangaUserSettingsResponse:
        """Get user settings."""
        settings = await self.repo.get_user_settings(user_id)
        if not settings:
            # Return default
            return MangaUserSettingsResponse(
                user_id=user_id,
                schema_version=1,
                data={},
                updated_at=None,  # type: ignore
            )
        return MangaUserSettingsResponse.model_validate(settings)

    async def update_settings(
        self,
        user_id: UUID,
        data: MangaUserSettingsUpdate,
    ) -> MangaUserSettingsResponse:
        """Update user settings."""
        settings = await self.repo.upsert_user_settings(
            user_id=user_id,
            schema_version=data.schema_version,
            data=data.data,
        )
        return MangaUserSettingsResponse.model_validate(settings)