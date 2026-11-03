"""Provider package: importing it registers all built-in providers."""

from .registry import (
    ProviderInfo,
    ServiceInfo,
    get_provider,
    get_providers,
    get_service,
    provider,
    service,
)

# Registration side effect. Add one import per provider module.
from . import youtube  # noqa: E402,F401

__all__ = [
    "ProviderInfo",
    "ServiceInfo",
    "get_provider",
    "get_providers",
    "get_service",
    "provider",
    "service",
]
