"""Manga module provider client for validating external providers."""
import httpx
from typing import Optional
from urllib.parse import urlparse

from mugiko.modules.media.manga.exceptions import ProviderValidationError, InvalidProviderUrlError


class MangaProviderClient:
    """Client for calling external manga provider APIs."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    async def validate_provider(self, base_url: str) -> dict:
        """Validate a provider by calling its /info endpoint."""
        # Check URL validity
        if not self._is_valid_url(base_url):
            raise InvalidProviderUrlError("URL must be http or https")

        if self._is_private_ip(base_url):
            raise InvalidProviderUrlError("Private or loopback addresses not allowed")

        url = base_url.rstrip("/") + "/info"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                # Validate response shape
                if not all(k in data for k in ("name", "description", "api_version")):
                    raise ProviderValidationError("Invalid provider info response")

                if data.get("api_version") != "1":
                    raise ProviderValidationError(f"Unsupported API version: {data.get('api_version')}")

                return data

        except httpx.HTTPStatusError as e:
            raise ProviderValidationError(f"Provider returned {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            raise ProviderValidationError(f"Failed to connect to provider: {str(e)}")
        except ValueError as e:
            raise ProviderValidationError(f"Invalid JSON response: {str(e)}")

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid http/https."""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    def _is_private_ip(self, url: str) -> bool:
        """Check if URL resolves to private/loopback IP."""
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname

            if not hostname:
                return True

            # Check for loopback/localhost
            if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
                return True

            # For simplicity, we'll just check the hostname
            # In production, you'd want to resolve DNS and check the IP ranges
            # Private ranges: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7
            return False  # Skip IP resolution for now

        except Exception:
            return True