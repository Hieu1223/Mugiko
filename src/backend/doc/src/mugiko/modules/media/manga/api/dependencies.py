"""Manga module API dependencies."""
from fastapi import Depends
from typing import AsyncGenerator

from mugiko.common.persistent.session import get_session_cm
from mugiko.modules.media.manga.persistent.repository import MangaRepository
from mugiko.modules.media.manga.service.provider_service import ProviderService
from mugiko.modules.media.manga.service.subscription_service import SubscriptionService
from mugiko.modules.media.manga.service.history_service import HistoryService
from mugiko.modules.media.manga.service.settings_service import SettingsService
from mugiko.modules.core.user_management.api.dependencies import get_auth_context
from mugiko.modules.core.user_management.service.dtos import AuthContext
from mugiko.builtin.manga import BuiltinProvider


async def get_manga_repo() -> AsyncGenerator[MangaRepository, None]:
    """Get manga repository."""
    async with get_session_cm() as session:
        yield MangaRepository(session)


async def get_provider_service(repo: MangaRepository = Depends(get_manga_repo)) -> ProviderService:
    """Get provider service."""
    from mugiko.common.config.config import settings
    return ProviderService(repo, settings.public_base_url)


async def get_subscription_service(repo: MangaRepository = Depends(get_manga_repo)) -> SubscriptionService:
    """Get subscription service."""
    return SubscriptionService(repo)


async def get_history_service(repo: MangaRepository = Depends(get_manga_repo)) -> HistoryService:
    """Get history service."""
    return HistoryService(repo)


async def get_settings_service(repo: MangaRepository = Depends(get_manga_repo)) -> SettingsService:
    """Get settings service."""
    return SettingsService(repo)


async def get_builtin_provider(repo: MangaRepository = Depends(get_manga_repo)) -> BuiltinProvider:
    """Get built-in provider."""
    from mugiko.common.config.config import settings
    return BuiltinProvider(repo, settings.public_base_url)