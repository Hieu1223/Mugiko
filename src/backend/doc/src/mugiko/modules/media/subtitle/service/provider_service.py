"""Provider service for subtitle module."""
from typing import List, Optional
from uuid import UUID
from mugiko.modules.media.subtitle.service.dtos import (
    SubtitleProviderCreate,
    SubtitleProviderResponse,
    SubtitleProviderServiceResponse,
    ProviderKind as ServiceProviderKind,
)
from mugiko.modules.media.subtitle.persistent.repository import SubtitleRepository
from mugiko.modules.media.subtitle.provider.factory import create_provider
from mugiko.modules.media.subtitle.provider.dtos import ProviderSyncDTO
from mugiko.modules.media.subtitle.exceptions import (
    ProviderNotFoundError,
    ProviderSyncError,
)
from mugiko.modules.media.subtitle.persistent.models import ProviderKind as ModelProviderKind


class ProviderService:
    """Service for managing subtitle providers."""

    def __init__(self, repo: SubtitleRepository):
        self.repo = repo

    async def create_provider(self, data: SubtitleProviderCreate) -> SubtitleProviderResponse:
        """Create a new subtitle provider."""
        provider = await self.repo.create_provider(
            name=data.name,
            kind=data.kind,
            base_url=data.base_url,
        )
        # Manually construct response to avoid greenlet issues with lazy loading
        return SubtitleProviderResponse(
            id=provider.id,
            name=provider.name,
            kind=provider.kind,
            base_url=provider.base_url,
            is_active=provider.is_active,
            last_synced_at=provider.last_synced_at,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            services=[],
        )

    async def get_provider(self, provider_id: UUID) -> SubtitleProviderResponse:
        """Get a provider by ID."""
        provider = await self.repo.get_provider(provider_id)
        if not provider:
            raise ProviderNotFoundError()
        return SubtitleProviderResponse(
            id=provider.id,
            name=provider.name,
            kind=provider.kind,
            base_url=provider.base_url,
            is_active=provider.is_active,
            last_synced_at=provider.last_synced_at,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
            services=[
                SubtitleProviderServiceResponse.model_validate(s) for s in provider.services
            ],
        )

    async def list_providers(self) -> List[SubtitleProviderResponse]:
        """List all active providers with their services."""
        providers = await self.repo.get_active_providers()
        return [
            SubtitleProviderResponse(
                id=p.id,
                name=p.name,
                kind=p.kind,
                base_url=p.base_url,
                is_active=p.is_active,
                last_synced_at=p.last_synced_at,
                created_at=p.created_at,
                updated_at=p.updated_at,
                services=[
                    SubtitleProviderServiceResponse.model_validate(s) for s in p.services
                ],
            )
            for p in providers
        ]

    async def sync_provider(self, provider_id: UUID) -> SubtitleProviderResponse:
        """Sync a provider with its source."""
        provider = await self.repo.get_provider(provider_id)
        if not provider:
            raise ProviderNotFoundError()

        # Create provider instance and sync
        # provider.kind is a SQLAlchemy Column, get its value
        kind_value = provider.kind.value if hasattr(provider.kind, 'value') else str(provider.kind)
        
        config = {"base_url": provider.base_url} if provider.base_url else None
        provider_instance = create_provider(kind_value, config)

        try:
            sync_data: ProviderSyncDTO = await provider_instance.sync()
        except Exception as e:
            raise ProviderSyncError(detail=f"Sync failed: {str(e)}")

        # Update services
        services_data = [
            {
                "service_key": s.service_key,
                "name": s.name,
                "options": s.options,
            }
            for s in sync_data.services
        ]
        await self.repo.upsert_services(provider_id, services_data)

        # Update last synced time
        await self.repo.update_provider_sync_time(provider_id)

        # Return updated provider
        updated_provider = await self.repo.get_provider(provider_id)
        return SubtitleProviderResponse.model_validate(updated_provider)

    async def delete_provider(self, provider_id: UUID) -> bool:
        """Delete a provider."""
        return await self.repo.delete_provider(provider_id)