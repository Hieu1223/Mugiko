"""Provider factory for subtitle module."""
from typing import Optional
from mugiko.modules.media.subtitle.provider.base import SubtitleProvider
from mugiko.modules.media.subtitle.provider.dtos import RemoteProviderConfigDTO, YouTubeProviderConfigDTO
from mugiko.modules.media.subtitle.provider.youtube_provider import YouTubeSubtitleProvider
from mugiko.modules.media.subtitle.provider.remote_provider import RemoteSubtitleProvider
from mugiko.modules.media.subtitle.persistent.models import ProviderKind
from mugiko.modules.media.subtitle.exceptions import InvalidProviderConfigError


def create_provider(kind: str | ProviderKind, config: Optional[dict] = None) -> SubtitleProvider:
    """Create a subtitle provider instance based on kind and config."""
    # Convert string to enum if needed
    if isinstance(kind, str):
        kind = ProviderKind(kind)

    if kind == ProviderKind.YOUTUBE:
        return YouTubeSubtitleProvider()
    elif kind == ProviderKind.REMOTE:
        if not config or "base_url" not in config:
            raise InvalidProviderConfigError("Remote provider requires base_url in config")
        remote_config = RemoteProviderConfigDTO(base_url=config["base_url"])
        return RemoteSubtitleProvider(remote_config)
    else:
        raise InvalidProviderConfigError(f"Unknown provider kind: {kind}")