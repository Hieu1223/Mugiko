"""Manga module API routes."""
from mugiko.modules.media.manga.api.routes import (
    providers,
    subscriptions,
    history,
    settings,
    builtin,
)

__all__ = ["providers", "subscriptions", "history", "settings", "builtin"]