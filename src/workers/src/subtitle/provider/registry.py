"""Declarative provider/service registry for the subtitle module.

A provider is a class decorated with ``@provider``; each invocable unit of
work is a method decorated with ``@service``. The worker is the only caller
of registry lookups and provider methods.

The registry is also the source of truth mirrored into ``subtitle_providers``
and ``subtitle_provider_services`` at worker startup (see
``persistent/registry_sync.py``).
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ServiceInfo:
    """A registered service (method) within a provider."""

    service_key: str
    name: str
    options: Dict[str, Any]
    func: Callable


@dataclass
class ProviderInfo:
    """A registered provider together with its services."""

    name: str
    kind: str
    base_url: Optional[str]
    cls: type
    services: List[ServiceInfo] = field(default_factory=list)

    def add_service(self, service_info: ServiceInfo) -> None:
        self.services.append(service_info)

    def get_service(self, service_key: str) -> Optional[ServiceInfo]:
        for service_info in self.services:
            if service_info.service_key == service_key:
                return service_info
        return None


_provider_registry: Dict[str, ProviderInfo] = {}


def provider(name: str, kind: str, base_url: Optional[str] = None):
    """Register a provider class under ``name``."""

    def decorator(cls):
        provider_info = ProviderInfo(
            name=name,
            kind=kind,
            base_url=base_url,
            cls=cls,
        )
        _provider_registry[name] = provider_info
        cls._provider_info = provider_info
        return cls

    return decorator


def service(
    service_key: str,
    name: str,
    options: Optional[Dict[str, Any]] = None,
):
    """Mark a provider method as an invocable service."""

    def decorator(func):
        func._service_key = service_key
        func._service_name = name
        func._service_options = dict(options or {})
        return func

    return decorator


def _collect_services_from_class(cls: type) -> None:
    provider_info = getattr(cls, "_provider_info", None)
    if provider_info is None:
        return

    provider_info.services.clear()
    for attr_name in dir(cls):
        if attr_name.startswith("_"):
            continue
        attr = getattr(cls, attr_name)
        if callable(attr) and hasattr(attr, "_service_key"):
            provider_info.add_service(
                ServiceInfo(
                    service_key=attr._service_key,
                    name=attr._service_name,
                    options=attr._service_options,
                    func=attr,
                )
            )


def get_providers() -> List[ProviderInfo]:
    """All registered providers, with their services collected."""
    for provider_info in _provider_registry.values():
        _collect_services_from_class(provider_info.cls)
    return list(_provider_registry.values())


def get_provider(name: str) -> Optional[ProviderInfo]:
    """Look up a provider by exact registered name."""
    provider_info = _provider_registry.get(name)
    if provider_info is None:
        return None
    _collect_services_from_class(provider_info.cls)
    return provider_info


def get_service(provider_name: str, service_key: str) -> Optional[ServiceInfo]:
    """Look up one service by provider name and service key."""
    provider_info = get_provider(provider_name)
    if provider_info is None:
        return None
    return provider_info.get_service(service_key)
