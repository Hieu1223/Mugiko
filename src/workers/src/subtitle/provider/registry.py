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
    auto_languages: Optional[List[str]] = None
    auto_service_key_template: str = "{kind}_{lang}"
    auto_service_name_template: str = "Generate {lang_name} Subtitles"

    def add_service(self, service_info: ServiceInfo) -> None:
        self.services.append(service_info)

    def get_service(self, service_key: str) -> Optional[ServiceInfo]:
        for service_info in self.services:
            if service_info.service_key == service_key:
                return service_info
        return None


_provider_registry: Dict[str, ProviderInfo] = {}


def provider(
    name: str,
    kind: str,
    base_url: Optional[str] = None,
    auto_languages: Optional[List[str]] = None,
    auto_service_key_template: str = "{kind}_{lang}",
    auto_service_name_template: str = "Generate {lang_name} Subtitles",
):
    """Register a provider class under ``name``.

    If ``auto_languages`` is provided, services are auto-generated for each
    language code. The provider class must implement a ``generate(self, url,
    language)`` method that returns a ``RawSubtitleArtifact``.
    """

    def decorator(cls):
        provider_info = ProviderInfo(
            name=name,
            kind=kind,
            base_url=base_url,
            cls=cls,
            auto_languages=auto_languages,
            auto_service_key_template=auto_service_key_template,
            auto_service_name_template=auto_service_name_template,
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

    # Auto-generate services for providers that declare auto_languages.
    if provider_info.auto_languages:
        lang_names = {
            "ja": "Japanese",
            "vi": "Vietnamese",
            "en": "English",
            "ko": "Korean",
            "zh": "Chinese",
            "fr": "French",
            "de": "German",
            "es": "Spanish",
            "pt": "Portuguese",
            "it": "Italian",
            "ru": "Russian",
        }
        generate_method = getattr(cls, "generate", None)
        if generate_method is not None:
            for lang in provider_info.auto_languages:
                lang_name = lang_names.get(lang, lang.upper())
                service_key = provider_info.auto_service_key_template.format(
                    kind=provider_info.kind, lang=lang
                )
                service_name = provider_info.auto_service_name_template.format(
                    lang_name=lang_name
                )

                # Create a bound wrapper that calls generate(url, language)
                def _make_func(lang_code: str):
                    def _auto_service(self, url: str):
                        return self.generate(url, lang_code)

                    _auto_service._service_key = service_key
                    _auto_service._service_name = service_name
                    _auto_service._service_options = {"language": lang_code}
                    return _auto_service

                func = _make_func(lang)
                # Store the unbound function; worker calls func(cls(), url)
                provider_info.add_service(
                    ServiceInfo(
                        service_key=service_key,
                        name=service_name,
                        options={"language": lang},
                        func=func,
                    )
                )

    # Collect manually decorated @service methods.
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
