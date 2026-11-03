"""Lookup provider package."""
from mugiko.modules.core.lookup.provider.dictionary_provider import (
    BinaryDictionaryProvider,
    KanjiDictionaryProvider,
    DictionaryEntry,
    KanjiEntry,
)

__all__ = [
    "BinaryDictionaryProvider",
    "KanjiDictionaryProvider",
    "DictionaryEntry",
    "KanjiEntry",
]