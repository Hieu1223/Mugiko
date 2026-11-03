"""User subtitle settings routes."""
from fastapi import APIRouter, Depends
from typing import Optional

from mugiko.modules.media.subtitle.api.schemas import (
    UserSettingsResponse,
    UserSettingsUpdate,
)
from mugiko.modules.media.subtitle.api.dependencies import get_subtitle_service
from mugiko.modules.media.subtitle.service.subtitle_service import SubtitleService
from mugiko.modules.core.user_management.api.dependencies import require_user
from mugiko.modules.core.user_management.service.dtos import AuthContext


router = APIRouter(prefix="/users/me", tags=["subtitle"])


@router.get(
    "/subtitle-settings",
    response_model=UserSettingsResponse,
)
async def get_user_settings(
    service: SubtitleService = Depends(get_subtitle_service),
    auth: AuthContext = Depends(require_user),
):
    """Get user's global subtitle settings."""
    return await service.get_user_settings(auth.user_id)


@router.put(
    "/subtitle-settings",
    response_model=UserSettingsResponse,
)
async def update_user_settings(
    data: UserSettingsUpdate,
    service: SubtitleService = Depends(get_subtitle_service),
    auth: AuthContext = Depends(require_user),
):
    """Update user's global subtitle settings."""
    return await service.update_user_settings(auth.user_id, data)