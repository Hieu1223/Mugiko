"""Subtitle provider routes."""
from fastapi import APIRouter, Depends, status
from uuid import UUID
from typing import List

from mugiko.modules.media.subtitle.api.schemas import (
    SubtitleProviderCreate as APISubtitleProviderCreate,
    SubtitleProviderResponse,
)
from mugiko.modules.media.subtitle.api.dependencies import get_provider_service
from mugiko.modules.media.subtitle.service.provider_service import ProviderService
from mugiko.modules.media.subtitle.service.dtos import (
    SubtitleProviderCreate as ServiceSubtitleProviderCreate,
)
from mugiko.modules.core.user_management.api.dependencies import require_admin, get_auth_context
from mugiko.modules.core.user_management.service.dtos import AuthContext


router = APIRouter(prefix="/subtitle-providers", tags=["subtitle"])


@router.get(
    "",
    response_model=List[SubtitleProviderResponse],
)
async def list_providers(
    service: ProviderService = Depends(get_provider_service),
):
    """List all active subtitle providers with their services."""
    return await service.list_providers()


@router.post(
    "",
    response_model=SubtitleProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(
    data: APISubtitleProviderCreate,
    service: ProviderService = Depends(get_provider_service),
    auth: AuthContext = Depends(require_admin),
):
    """Create a new subtitle provider (admin only)."""
    service_data = ServiceSubtitleProviderCreate(
        name=data.name,
        kind=data.kind,
        base_url=data.base_url,
    )
    return await service.create_provider(service_data)


@router.post(
    "/{provider_id}/sync",
    response_model=SubtitleProviderResponse,
)
async def sync_provider(
    provider_id: UUID,
    service: ProviderService = Depends(get_provider_service),
    auth: AuthContext = Depends(require_admin),
):
    """Sync a provider with its source (admin only)."""
    return await service.sync_provider(provider_id)