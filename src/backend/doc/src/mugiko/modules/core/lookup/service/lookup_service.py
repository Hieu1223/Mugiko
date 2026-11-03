"""Lookup service for dictionary and kanji lookups."""
from typing import List, Optional
from dataclasses import dataclass

from mugiko.modules.core.lookup.provider.dictionary_provider import (
    BinaryDictionaryProvider,
    KanjiDictionaryProvider,
    DictionaryEntry as ProviderDictionaryEntry,
    KanjiEntry as ProviderKanjiEntry,
)
from mugiko.modules.core.lookup.exceptions import (
    DictionaryNotFoundError,
    DictionaryCorruptedError,
    WordNotFoundError,
    KanjiNotFoundError,
    InvalidKanjiError,
)


@dataclass
class DictionaryEntry:
    """Dictionary entry for API response."""
    word: str
    readings: List[dict]  # [{"kana": "...", "meaning": "..."}]


@dataclass
class KanjiEntry:
    """Kanji entry for API response."""
    kanji: str
    reading: str
    meanings: str
    strokes: int
    radical: str
    penstrokes: str
    shape: str
    unicode: str


@dataclass
class PrefixSearchResult:
    """Prefix search result."""
    entries: List[DictionaryEntry]
    count: int


class LookupService:
    """Service for dictionary and kanji lookups."""

    def __init__(
        self,
        dictionary_path: str = "asset/dictionary.bin",
        kanji_dictionary_path: str = "asset/kanji_dictionary.bin",
    ):
        self.dictionary_path = dictionary_path
        self.kanji_dictionary_path = kanji_dictionary_path

    def lookup_word(self, word: str) -> DictionaryEntry:
        """Look up a word in the dictionary."""
        try:
            with BinaryDictionaryProvider(self.dictionary_path) as provider:
                entry = provider.lookup(word)
                if entry:
                    return self._convert_dict_entry(entry)
        except DictionaryNotFoundError:
            raise
        except DictionaryCorruptedError:
            raise
        raise WordNotFoundError(f"Word '{word}' not found")

    def prefix_search(self, prefix: str, limit: int = 100) -> PrefixSearchResult:
        """Search for words starting with prefix."""
        try:
            with BinaryDictionaryProvider(self.dictionary_path) as provider:
                entries = provider.prefix_search(prefix, limit)
                return PrefixSearchResult(
                    entries=[self._convert_dict_entry(e) for e in entries],
                    count=len(entries),
                )
        except DictionaryNotFoundError:
            raise
        except DictionaryCorruptedError:
            raise

    def lookup_kanji(self, kanji: str) -> KanjiEntry:
        """Look up a single kanji character."""
        if len(kanji) != 1:
            raise InvalidKanjiError("Input must be a single kanji character")

        try:
            with KanjiDictionaryProvider(self.kanji_dictionary_path) as provider:
                entry = provider.lookup(kanji)
                if entry:
                    return self._convert_kanji_entry(entry)
        except DictionaryNotFoundError:
            raise
        except DictionaryCorruptedError:
            raise
        raise KanjiNotFoundError(f"Kanji '{kanji}' not found")

    def _convert_dict_entry(self, entry: ProviderDictionaryEntry) -> DictionaryEntry:
        """Convert provider dictionary entry to service entry."""
        return DictionaryEntry(
            word=entry.word,
            readings=[{"kana": kana, "meaning": meaning} for kana, meaning in entry.readings],
        )

    def _convert_kanji_entry(self, entry: ProviderKanjiEntry) -> KanjiEntry:
        """Convert provider kanji entry to service entry."""
        return KanjiEntry(
            kanji=entry.kanji,
            reading=entry.reading,
            meanings=entry.meanings,
            strokes=entry.strokes,
            radical=entry.radical,
            penstrokes=entry.penstrokes,
            shape=entry.shape,
            unicode=entry.unicode,
        )