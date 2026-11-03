"""Exceptions package."""
from mugiko.modules.media.web_novel.exceptions.web_novel_exceptions import (
    WebNovelException,
    NovelNotFoundError,
    NovelAlreadyExistsError,
    InvalidUrlError,
    ProviderError,
    SyncError,
)

__all__ = [
    "WebNovelException",
    "NovelNotFoundError",
    "NovelAlreadyExistsError",
    "InvalidUrlError",
    "ProviderError",
    "SyncError",
]