"""Subtitle user state routes."""
from fastapi import APIRouter, Depends
from uuid import UUID

from mugiko.modules.media.subtitle.api.schemas import (
    SubtitleUserStateResponse,
    SubtitleUserStateUpdate,
)
from mugiko.modules.media.subtitle.api.dependencies import get_subtitle_service
from mugiko.modules.media.subtitle.service.subtitle_service import SubtitleService
from mugiko.modules.core.user_management.api.dependencies import require_user
from mugiko.modules.core.user_management.service.dtos import AuthContext


router = APIRouter(prefix="/subtitles", tags=["subtitle"])


@router.get(
    "/{subtitle_id}/state",
    response_model=SubtitleUserStateResponse,
)
async def get_subtitle_user_state(
    subtitle_id: UUID,
    service: SubtitleService = Depends(get_subtitle_service),
    auth: AuthContext = Depends(require_user),
):
    """Get user's state for a specific subtitle (e.g., video progress)."""
    return await service.get_subtitle_user_state(auth.user_id, subtitle_id)


@router.put(
    "/{subtitle_id}/state",
    response_model=SubtitleUserStateResponse,
)
async def update_subtitle_user_state(
    subtitle_id: UUID,
    data: SubtitleUserStateUpdate,
    service: SubtitleService = Depends(get_subtitle_service),
    auth: AuthContext = Depends(require_user),
):
    """Update user's state for a specific subtitle (e.g., video progress)."""
    return await service.update_subtitle_user_state(auth.user_id, subtitle_id, data)