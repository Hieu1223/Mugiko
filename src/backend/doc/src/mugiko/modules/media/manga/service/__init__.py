"""Manga module service package."""
from mugiko.modules.media.manga.service.provider_service import ProviderService
from mugiko.modules.media.manga.service.subscription_service import SubscriptionService
from mugiko.modules.media.manga.service.history_service import HistoryService
from mugiko.modules.media.manga.service.settings_service import SettingsService

__all__ = [
    "ProviderService",
    "SubscriptionService",
    "HistoryService",
    "SettingsService",
]