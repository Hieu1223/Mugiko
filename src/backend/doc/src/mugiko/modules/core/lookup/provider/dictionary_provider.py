"""Dictionary provider for binary dictionary lookup (word and kanji)."""
import struct
import mmap
from pathlib import Path
from typing import Optional, List, Tuple, BinaryIO
from dataclasses import dataclass

from mugiko.modules.core.lookup.exceptions import (
    DictionaryNotFoundError,
    DictionaryCorruptedError,
    WordNotFoundError,
    KanjiNotFoundError,
)


@dataclass
class DictionaryEntry:
    """Represents a dictionary entry with readings and meanings."""
    word: str
    readings: List[Tuple[str, str]]  # (kana, meaning)


@dataclass
class KanjiEntry:
    """Represents a kanji dictionary entry."""
    kanji: str
    reading: str
    meanings: str
    strokes: int
    radical: str
    penstrokes: str
    shape: str
    unicode: str


class BinaryDictionaryProvider:
    """Provider for binary dictionary format (MUGI)."""

    MAGIC = b"MUGI"
    VERSION = 1

    def __init__(self, dict_path: str):
        self.dict_path = Path(dict_path)
        self._data: Optional[mmap.mmap] = None
        self._file: Optional[BinaryIO] = None
        self._trie_start = 0
        self._def_start = 0
        self._entry_count = 0

    def __enter__(self) -> "BinaryDictionaryProvider":
        try:
            self._file = open(self.dict_path, "rb")
        except FileNotFoundError:
            raise DictionaryNotFoundError(f"Dictionary file not found: {self.dict_path}")
        self._data = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
        self._parse_header()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._data:
            self._data.close()
            self._data = None
        if self._file:
            self._file.close()
            self._file = None

    def _parse_header(self):
        """Parse the 24-byte header."""
        assert self._data is not None
        if len(self._data) < 24:
            raise DictionaryCorruptedError("File too small for header")

        magic = self._data[0:4]
        if magic != self.MAGIC:
            raise DictionaryCorruptedError(f"Invalid magic: {magic}, expected {self.MAGIC}")

        version = struct.unpack("<I", self._data[4:8])[0]
        if version != self.VERSION:
            raise DictionaryCorruptedError(f"Unsupported version: {version}")

        self._trie_start = struct.unpack("<I", self._data[8:12])[0]
        self._def_start = struct.unpack("<I", self._data[12:16])[0]
        self._entry_count = struct.unpack("<I", self._data[16:20])[0]

    def _read_u32(self, offset: int) -> int:
        assert self._data is not None
        return struct.unpack("<I", self._data[offset:offset+4])[0]

    def _read_definition(self, offset: int) -> List[Tuple[str, str]]:
        """Read null-terminated definition string at offset."""
        assert self._data is not None
        end = offset
        while end < len(self._data) and self._data[end] != 0:
            end += 1
        def_str = self._data[offset:end].decode("utf-8")
        parts = def_str.split("|")
        result = []
        for i in range(0, len(parts) - 1, 2):
            kana = parts[i]
            mean = parts[i + 1]
            result.append((kana, mean))
        return result

    def lookup(self, word: str) -> Optional[DictionaryEntry]:
        """Look up a word in the dictionary."""
        assert self._data is not None
        node_offset = self._trie_start
        for char in word:
            table_size = self._read_u32(node_offset)
            def_addr = self._read_u32(node_offset + 4)
            char_code = ord(char)
            child_base = node_offset + 8
            hash_val = char_code % table_size

            for _ in range(table_size):
                child_offset = child_base + hash_val * 8
                stored_char = self._read_u32(child_offset)
                addr = self._read_u32(child_offset + 4)
                if stored_char == 0 and addr == 0:
                    return None
                if stored_char == char_code:
                    node_offset = addr
                    break
                hash_val = (hash_val + 1) % table_size
            else:
                return None

        # Check final node for definition
        table_size = self._read_u32(node_offset)
        def_addr = self._read_u32(node_offset + 4)
        if def_addr != 0:
            readings = self._read_definition(def_addr)
            return DictionaryEntry(word=word, readings=readings)
        return None

    def prefix_search(self, prefix: str, limit: int = 100) -> List[DictionaryEntry]:
        """Find all words starting with prefix."""
        assert self._data is not None
        node_offset = self._trie_start
        for char in prefix:
            table_size = self._read_u32(node_offset)
            child_base = node_offset + 8
            char_code = ord(char)
            hash_val = char_code % table_size

            found = False
            for _ in range(table_size):
                child_offset = child_base + hash_val * 8
                stored_char = self._read_u32(child_offset)
                addr = self._read_u32(child_offset + 4)
                if stored_char == 0 and addr == 0:
                    return []
                if stored_char == char_code:
                    node_offset = addr
                    found = True
                    break
                hash_val = (hash_val + 1) % table_size
            if not found:
                return []

        results = []
        self._dfs_collect(node_offset, prefix, results, limit)
        return results

    def _dfs_collect(self, node_offset: int, current_word: str, results: List[DictionaryEntry], limit: int):
        assert self._data is not None
        if len(results) >= limit:
            return

        table_size = self._read_u32(node_offset)
        def_addr = self._read_u32(node_offset + 4)

        if def_addr != 0:
            readings = self._read_definition(def_addr)
            results.append(DictionaryEntry(word=current_word, readings=readings))
            if len(results) >= limit:
                return

        child_base = node_offset + 8
        for i in range(table_size):
            child_offset = child_base + i * 8
            stored_char = self._read_u32(child_offset)
            addr = self._read_u32(child_offset + 4)
            if stored_char != 0 and addr != 0:
                char = chr(stored_char)
                self._dfs_collect(addr, current_word + char, results, limit)
                if len(results) >= limit:
                    return


class KanjiDictionaryProvider:
    """Provider for kanji dictionary format (KANJ) - open-addressing hash map."""

    MAGIC = b"KANJ"
    VERSION = 1

    def __init__(self, dict_path: str):
        self.dict_path = Path(dict_path)
        self._data: Optional[mmap.mmap] = None
        self._file: Optional[BinaryIO] = None
        self._table_size = 0
        self._entry_count = 0
        self._entries_start = 0

    def __enter__(self) -> "KanjiDictionaryProvider":
        try:
            self._file = open(self.dict_path, "rb")
        except FileNotFoundError:
            raise DictionaryNotFoundError(f"Kanji dictionary file not found: {self.dict_path}")
        self._data = mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ)
        self._parse_header()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._data:
            self._data.close()
            self._data = None
        if self._file:
            self._file.close()
            self._file = None

    def _parse_header(self):
        assert self._data is not None
        if len(self._data) < 16:
            raise DictionaryCorruptedError("File too small for header")

        magic = self._data[0:4]
        if magic != self.MAGIC:
            raise DictionaryCorruptedError(f"Invalid magic: {magic}, expected {self.MAGIC}")

        version = struct.unpack("<I", self._data[4:8])[0]
        self._table_size = struct.unpack("<I", self._data[8:12])[0]
        self._entry_count = struct.unpack("<I", self._data[12:16])[0]
        self._entries_start = 16

    def _read_u32(self, offset: int) -> int:
        assert self._data is not None
        return struct.unpack("<I", self._data[offset:offset+4])[0]

    def _read_definition(self, offset: int) -> KanjiEntry:
        """Read kanji definition: kanji|reading|meanings|strokes|radical|penstrokes|shape|unicode\0"""
        assert self._data is not None
        end = offset
        while end < len(self._data) and self._data[end] != 0:
            end += 1
        def_str = self._data[offset:end].decode("utf-8")
        parts = def_str.split("|")
        if len(parts) < 8:
            raise ValueError(f"Invalid kanji definition format: {def_str}")

        return KanjiEntry(
            kanji=parts[0],
            reading=parts[1],
            meanings=parts[2],
            strokes=int(parts[3]) if parts[3].isdigit() else 0,
            radical=parts[4],
            penstrokes=parts[5],
            shape=parts[6],
            unicode=parts[7],
        )

    def lookup(self, kanji: str) -> Optional[KanjiEntry]:
        """Look up a single kanji character."""
        assert self._data is not None
        if len(kanji) != 1:
            return None

        char_code = ord(kanji)
        hash_val = char_code % self._table_size

        for _ in range(self._table_size):
            entry_offset = self._entries_start + hash_val * 8
            if entry_offset + 8 > len(self._data):
                return None

            stored_char = self._read_u32(entry_offset)
            addr = self._read_u32(entry_offset + 4)

            if stored_char == 0 and addr == 0:
                return None

            if stored_char == char_code:
                return self._read_definition(addr)

            hash_val = (hash_val + 1) % self._table_size

        return None