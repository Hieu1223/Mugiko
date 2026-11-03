"""Remote subtitle provider using HTTP client."""
import httpx
from typing import Optional

from mugiko.modules.media.subtitle.provider.base import SubtitleProvider
from mugiko.modules.media.subtitle.provider.dtos import (
    ProviderSyncDTO,
    ProviderServiceDTO,
    SubtitleResultDTO,
    SubtitleSegmentProviderDTO,
    SubtitleWordDTO,
    RemoteProviderConfigDTO,
)


class RemoteSubtitleProvider(SubtitleProvider):
    """Remote subtitle provider - calls external subtitle generation server."""

    def __init__(self, config: RemoteProviderConfigDTO):
        self.base_url = config.base_url.rstrip("/")
        self.provider_name = "Remote"
        self.provider_kind = "remote"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=300.0)  # 5 min timeout for generation
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def sync(self) -> ProviderSyncDTO:
        """Sync provider info and available services from remote server."""
        client = await self._get_client()
        try:
            response = await client.get(f"{self.base_url}/api/v1/sync")
            response.raise_for_status()
            data = response.json()

            services = [
                ProviderServiceDTO(
                    service_key=s["service_key"],
                    name=s["name"],
                    options=s.get("options"),
                )
                for s in data.get("services", [])
            ]

            return ProviderSyncDTO(
                provider_name=data.get("provider_name", "Remote Provider"),
                provider_kind="remote",
                services=services,
            )
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to sync with remote provider: {e}")

    async def get_subtitle(self, video_url: str, service_key: str) -> SubtitleResultDTO:
        """Request subtitle generation from remote server."""
        client = await self._get_client()
        try:
            # Synchronous call per plan default
            response = await client.post(
                f"{self.base_url}/api/v1/subtitles",
                json={"video_url": video_url, "service_key": service_key},
            )
            response.raise_for_status()
            data = response.json()

            segments = [
                SubtitleSegmentProviderDTO(
                    idx=s["idx"],
                    start_ms=s["start_ms"],
                    end_ms=s["end_ms"],
                    words=[
                        SubtitleWordDTO(
                            text=w["text"],
                            start_ms=w.get("start_ms"),
                            end_ms=w.get("end_ms"),
                        )
                        for w in s.get("words", [])
                    ] if s.get("words") else None,
                )
                for s in data.get("segments", [])
            ]

            return SubtitleResultDTO(
                video_id=data.get("video_id", ""),
                video_url=video_url,
                segments=segments,
            )
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to get subtitle from remote provider: {e}")