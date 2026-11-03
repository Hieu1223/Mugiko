"""Manga provider routes."""
from fastapi import APIRouter, Depends, status, Query
from uuid import UUID
from typing import List, Optional

from mugiko.modules.media.manga.api.schemas import (
    MangaProviderCreate as APIMangaProviderCreate,
    MangaProviderUpdate as APIMangaProviderUpdate,
    MangaProviderResponse,
)
from mugiko.modules.media.manga.api.dependencies import get_provider_service
from mugiko.modules.media.manga.service.provider_service import ProviderService
from mugiko.modules.media.manga.service.dtos import (
    MangaProviderCreate as ServiceMangaProviderCreate,
    MangaProviderUpdate as ServiceMangaProviderUpdate,
)
from mugiko.modules.core.user_management.api.dependencies import require_user, require_admin, get_auth_context
from mugiko.modules.core.user_management.service.dtos import AuthContext, Role

router = APIRouter(prefix="/manga/providers", tags=["manga"])


@router.get(
    "/mine",
    response_model=List[MangaProviderResponse],
)
async def list_my_providers(
    service: ProviderService = Depends(get_provider_service),
    auth: AuthContext = Depends(require_user),
):
    """List providers owned by current user."""
    return await service.get_user_providers(auth.user_id)


@router.get(
    "/public",
    response_model=List[MangaProviderResponse],
)
async def list_public_providers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: ProviderService = Depends(get_provider_service),
):
    """List public providers."""
    providers, _ = await service.get_public_providers(page=page, page_size=page_size)
    return providers


@router.post(
    "",
    response_model=MangaProviderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider(
    data: APIMangaProviderCreate,
    service: ProviderService = Depends(get_provider_service),
    auth: AuthContext = Depends(require_user),
):
    """Create a new manga provider."""
    service_data = ServiceMangaProviderCreate(
        name=data.name,
        base_url=data.base_url,
        visibility=data.visibility,
    )
    return await service.create_provider(service_data, auth)


@router.patch(
    "/{provider_id}",
    response_model=MangaProviderResponse,
)
async def update_provider(
    provider_id: UUID,
    data: APIMangaProviderUpdate,
    service: ProviderService = Depends(get_provider_service),
    auth: AuthContext = Depends(require_user),
):
    """Update a provider (owner only)."""
    service_data = ServiceMangaProviderUpdate(
        name=data.name,
        base_url=data.base_url,
        visibility=data.visibility,
    )
    return await service.update_provider(provider_id, service_data, auth)


@router.delete(
    "/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_provider(
    provider_id: UUID,
    service: ProviderService = Depends(get_provider_service),
    auth: AuthContext = Depends(require_user),
):
    """Delete a provider (owner only)."""
    await service.delete_provider(provider_id, auth)