"""Manga module provider service."""
from typing import List
from uuid import UUID

from mugiko.modules.media.manga.service.dtos import (
    MangaProviderCreate,
    MangaProviderUpdate,
    MangaProviderResponse,
    ProviderVisibility,
)
from mugiko.modules.media.manga.persistent.repository import MangaRepository
from mugiko.modules.media.manga.provider.client import MangaProviderClient
from mugiko.modules.media.manga.exceptions import (
    ProviderNotFoundError,
    ProviderValidationError,
    ForbiddenError,
    InvalidProviderUrlError,
)
from mugiko.modules.core.user_management.service.dtos import AuthContext, Role


class ProviderService:
    """Service for managing manga providers."""

    def __init__(self, repo: MangaRepository, public_base_url: str):
        self.repo = repo
        self.client = MangaProviderClient()
        self.public_base_url = public_base_url

    async def create_provider(
        self,
        data: MangaProviderCreate,
        auth: AuthContext,
    ) -> MangaProviderResponse:
        """Create a new manga provider."""
        # Check for duplicate
        existing = await self.repo.get_provider_by_owner_and_url(auth.user_id, data.base_url)
        if existing:
            raise ProviderValidationError("Provider with this URL already exists")

        # Validate provider by calling /info (skip for built-in)
        if not data.base_url.startswith(self.public_base_url):
            await self.client.validate_provider(data.base_url)

        provider = await self.repo.create_provider(
            owner_id=auth.user_id,
            name=data.name,
            base_url=data.base_url,
            visibility=data.visibility,
        )

        return MangaProviderResponse.model_validate(provider)

    async def get_provider(self, provider_id: UUID) -> MangaProviderResponse:
        """Get provider by ID."""
        provider = await self.repo.get_provider(provider_id)
        if not provider:
            raise ProviderNotFoundError()
        return MangaProviderResponse.model_validate(provider)

    async def get_user_providers(self, user_id: UUID) -> List[MangaProviderResponse]:
        """Get providers owned by user."""
        providers = await self.repo.get_user_providers(user_id)
        return [MangaProviderResponse.model_validate(p) for p in providers]

    async def get_public_providers(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[MangaProviderResponse], int]:
        """Get public providers with pagination."""
        providers, total = await self.repo.get_public_providers(page=page, page_size=page_size)
        return [MangaProviderResponse.model_validate(p) for p in providers], total

    async def update_provider(
        self,
        provider_id: UUID,
        data: MangaProviderUpdate,
        auth: AuthContext,
    ) -> MangaProviderResponse:
        """Update provider (owner only)."""
        provider = await self.repo.get_provider(provider_id)
        if not provider:
            raise ProviderNotFoundError()

        # Check ownership
        if provider.owner_id != auth.user_id and auth.role != Role.ADMIN:
            raise ForbiddenError("Only the owner can update this provider")

        # Validate new URL if changed
        if data.base_url and data.base_url != provider.base_url:
            if not data.base_url.startswith(self.public_base_url):
                await self.client.validate_provider(data.base_url)
            # Check for duplicate
            existing = await self.repo.get_provider_by_owner_and_url(provider.owner_id, data.base_url)
            if existing and existing.id != provider_id:
                raise ProviderValidationError("Provider with this URL already exists")

        # Update
        updated = await self.repo.update_provider(
            provider,
            name=data.name,
            base_url=data.base_url,
            visibility=data.visibility,
        )

        return MangaProviderResponse.model_validate(updated)

    async def delete_provider(self, provider_id: UUID, auth: AuthContext) -> bool:
        """Delete provider (owner only)."""
        provider = await self.repo.get_provider(provider_id)
        if not provider:
            raise ProviderNotFoundError()

        # Check ownership
        if provider.owner_id != auth.user_id and auth.role != Role.ADMIN:
            raise ForbiddenError("Only the owner can delete this provider")

        # Prevent deleting built-in provider
        if provider.is_builtin:
            raise ForbiddenError("Cannot delete built-in provider")

        return await self.repo.delete_provider(provider_id)