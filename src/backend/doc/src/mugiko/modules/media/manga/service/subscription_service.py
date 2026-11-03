"""Manga module subscription service."""
from typing import List
from uuid import UUID

from mugiko.modules.media.manga.service.dtos import (
    MangaSubscriptionResponse,
    MangaProviderResponse,
)
from mugiko.modules.media.manga.persistent.repository import MangaRepository
from mugiko.modules.media.manga.exceptions import (
    ProviderNotFoundError,
    ForbiddenError,
    AlreadySubscribedError,
)
from mugiko.modules.core.user_management.service.dtos import AuthContext, Role


class SubscriptionService:
    """Service for managing manga subscriptions."""

    def __init__(self, repo: MangaRepository):
        self.repo = repo

    async def subscribe(
        self,
        provider_id: UUID,
        auth: AuthContext,
    ) -> MangaSubscriptionResponse:
        """Subscribe to a provider."""
        provider = await self.repo.get_provider(provider_id)
        if not provider:
            raise ProviderNotFoundError()

        # Check if provider is subscribable
        if provider.visibility.value == "private" and provider.owner_id != auth.user_id and auth.role != Role.ADMIN:
            raise ForbiddenError("Cannot subscribe to private provider")

        # Check if already subscribed
        existing = await self.repo.get_subscription(auth.user_id, provider_id)
        if existing:
            raise AlreadySubscribedError()

        # Create subscription
        subscription = await self.repo.subscribe(auth.user_id, provider_id)

        return MangaSubscriptionResponse(
            user_id=subscription.user_id,
            provider_id=subscription.provider_id,
            created_at=subscription.created_at,
            provider=MangaProviderResponse.model_validate(provider),
        )

    async def unsubscribe(self, provider_id: UUID, auth: AuthContext) -> bool:
        """Unsubscribe from a provider."""
        provider = await self.repo.get_provider(provider_id)
        if not provider:
            raise ProviderNotFoundError()

        return await self.repo.unsubscribe(auth.user_id, provider_id)

    async def get_user_subscriptions(self, user_id: UUID) -> List[MangaSubscriptionResponse]:
        """Get user's subscriptions."""
        subscriptions = await self.repo.get_user_subscriptions(user_id)
        return [
            MangaSubscriptionResponse(
                user_id=s.user_id,
                provider_id=s.provider_id,
                created_at=s.created_at,
                provider=MangaProviderResponse.model_validate(s.provider) if s.provider else None,
            )
            for s in subscriptions
        ]

    async def get_subscribable_providers(self, user_id: UUID) -> List[MangaProviderResponse]:
        """Get providers user can subscribe to."""
        providers = await self.repo.get_subscribable_providers(user_id)
        return [MangaProviderResponse.model_validate(p) for p in providers]