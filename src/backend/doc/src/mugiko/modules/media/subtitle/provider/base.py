"""Provider base interface for subtitle module."""
from typing import Protocol
from mugiko.modules.media.subtitle.provider.dtos import ProviderSyncDTO, SubtitleResultDTO


class SubtitleProvider(Protocol):
    """Protocol for subtitle providers."""

    async def sync(self) -> ProviderSyncDTO:
        """Sync provider info and available services."""
        ...

    async def get_subtitle(self, video_url: str, service_key: str) -> SubtitleResultDTO:
        """Get subtitle for a video using a specific service."""
        ...