"""Subtitle routes."""
from fastapi import APIRouter, Depends, Query, status, Response
from uuid import UUID
from typing import List, Optional

from mugiko.modules.media.subtitle.api.schemas import (
    SubtitleCreate as APISubtitleCreate,
    SubtitleResponse,
    SubtitleListResponse,
)
from mugiko.modules.media.subtitle.api.dependencies import get_subtitle_service
from mugiko.modules.media.subtitle.service.subtitle_service import SubtitleService
from mugiko.modules.media.subtitle.service.dtos import (
    SubtitleCreate as ServiceSubtitleCreate,
)
from mugiko.modules.core.user_management.api.dependencies import require_user, get_auth_context
from mugiko.modules.core.user_management.service.dtos import AuthContext


router = APIRouter(prefix="/subtitles", tags=["subtitle"])


@router.post(
    "",
    response_model=SubtitleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subtitle(
    data: APISubtitleCreate,
    response: Response,
    service: SubtitleService = Depends(get_subtitle_service),
    auth: AuthContext = Depends(require_user),
):
    """Create a new subtitle and start generation job."""
    service_data = ServiceSubtitleCreate(
        video_url=data.video_url,
        provider_id=data.provider_id,
        service_key=data.service_key,
    )
    subtitle = await service.create_subtitle(auth.user_id, service_data)
    response.headers["Authorization"] = f"Bearer user-***"
    return subtitle


@router.get(
    "",
    response_model=List[SubtitleListResponse],
)
async def search_subtitles(
    video_url: str = Query(..., description="YouTube video URL"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    service: SubtitleService = Depends(get_subtitle_service),
):
    """Search subtitles by video URL with pagination."""
    return await service.search_subtitles(video_url, limit=limit, offset=offset)


@router.get(
    "/{subtitle_id}",
    response_model=SubtitleResponse,
)
async def get_subtitle(
    subtitle_id: UUID,
    response: Response,
    limit: int = Query(100, ge=1, le=500, description="Maximum number of segments"),
    offset: int = Query(0, ge=0, description="Number of segments to skip"),
    service: SubtitleService = Depends(get_subtitle_service),
    auth: Optional[AuthContext] = Depends(get_auth_context),
):
    """Get a subtitle by ID with paginated segments."""
    user_id = auth.user_id if auth else None
    subtitle = await service.get_subtitle(subtitle_id, user_id, limit=limit, offset=offset)
    if auth:
        response.headers["Authorization"] = f"Bearer user-***"
    return subtitle