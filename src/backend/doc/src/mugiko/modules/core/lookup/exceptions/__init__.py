"""Lookup module exceptions."""
from mugiko.modules.core.user_management.exceptions import UserManagementException
from .dictionary import (
    DictionaryNotFoundError,
    DictionaryCorruptedError,
    WordNotFoundError,
    KanjiNotFoundError,
    InvalidKanjiError,
)

__all__ = [
    "DictionaryNotFoundError",
    "DictionaryCorruptedError",
    "WordNotFoundError",
    "KanjiNotFoundError",
    "InvalidKanjiError",
]