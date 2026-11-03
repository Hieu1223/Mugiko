"""Manga settings routes."""
from fastapi import APIRouter, Depends
from uuid import UUID

from mugiko.modules.media.manga.api.schemas import (
    MangaUserSettingsResponse as APIMangaUserSettingsResponse,
    MangaUserSettingsUpdate as APIMangaUserSettingsUpdate,
)
from mugiko.modules.media.manga.api.dependencies import get_settings_service
from mugiko.modules.media.manga.service.settings_service import SettingsService
from mugiko.modules.media.manga.service.dtos import (
    MangaUserSettingsUpdate as ServiceMangaUserSettingsUpdate,
)
from mugiko.modules.core.user_management.api.dependencies import require_user
from mugiko.modules.core.user_management.service.dtos import AuthContext

router = APIRouter(prefix="/manga", tags=["manga"])


@router.get(
    "/settings",
    response_model=APIMangaUserSettingsResponse,
)
async def get_settings(
    service: SettingsService = Depends(get_settings_service),
    auth: AuthContext = Depends(require_user),
):
    """Get user settings."""
    return await service.get_settings(auth.user_id)


@router.put(
    "/settings",
    response_model=APIMangaUserSettingsResponse,
)
async def update_settings(
    data: APIMangaUserSettingsUpdate,
    service: SettingsService = Depends(get_settings_service),
    auth: AuthContext = Depends(require_user),
):
    """Update user settings."""
    service_data = ServiceMangaUserSettingsUpdate(
        schema_version=data.schema_version,
        data=data.data,
    )
    return await service.update_settings(auth.user_id, service_data)