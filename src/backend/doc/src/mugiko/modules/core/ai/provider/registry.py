from typing import Optional
from mugiko.modules.core.ai.provider.base import AIServiceProvider
from mugiko.modules.core.ai.provider.nim import NimProvider


class ProviderRegistry:
    """Registry mapping service keys to provider instances."""
    
    def __init__(self):
        self._providers: dict[str, AIServiceProvider] = {}
        self._register_defaults()
    
    def _register_defaults(self) -> None:
        self.register(NimProvider())
    
    def register(self, provider: AIServiceProvider) -> None:
        self._providers[provider.service_key] = provider
    
    def get(self, service_key: str) -> Optional[AIServiceProvider]:
        return self._providers.get(service_key)
    
    def list_services(self) -> list[str]:
        return list(self._providers.keys())


provider_registry = ProviderRegistry()