"""Manga subscription routes."""
from fastapi import APIRouter, Depends, status, Query
from uuid import UUID
from typing import List

from mugiko.modules.media.manga.api.schemas import (
    MangaSubscriptionResponse,
    MangaProviderResponse,
)
from mugiko.modules.media.manga.api.dependencies import get_subscription_service
from mugiko.modules.media.manga.service.subscription_service import SubscriptionService
from mugiko.modules.core.user_management.api.dependencies import require_user
from mugiko.modules.core.user_management.service.dtos import AuthContext

router = APIRouter(prefix="/manga", tags=["manga"])


@router.post(
    "/providers/{provider_id}/subscribe",
    response_model=MangaSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def subscribe_to_provider(
    provider_id: UUID,
    service: SubscriptionService = Depends(get_subscription_service),
    auth: AuthContext = Depends(require_user),
):
    """Subscribe to a provider."""
    result = await service.subscribe(provider_id, auth)
    return result


@router.delete(
    "/providers/{provider_id}/subscribe",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unsubscribe_from_provider(
    provider_id: UUID,
    service: SubscriptionService = Depends(get_subscription_service),
    auth: AuthContext = Depends(require_user),
):
    """Unsubscribe from a provider."""
    await service.unsubscribe(provider_id, auth)


@router.get(
    "/subscriptions",
    response_model=List[MangaSubscriptionResponse],
)
async def list_subscriptions(
    service: SubscriptionService = Depends(get_subscription_service),
    auth: AuthContext = Depends(require_user),
):
    """List current user's subscriptions."""
    return await service.get_user_subscriptions(auth.user_id)


@router.get(
    "/providers/subscribable",
    response_model=List[MangaProviderResponse],
)
async def list_subscribable_providers(
    service: SubscriptionService = Depends(get_subscription_service),
    auth: AuthContext = Depends(require_user),
):
    """List providers the user can subscribe to."""
    return await service.get_subscribable_providers(auth.user_id)