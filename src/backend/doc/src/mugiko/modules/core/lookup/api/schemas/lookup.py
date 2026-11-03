"""API schemas for lookup module."""
from typing import List, Optional
from pydantic import BaseModel, Field


class DictionaryReadingSchema(BaseModel):
    """Single reading/meaning pair."""
    kana: str
    meaning: str


class DictionaryEntrySchema(BaseModel):
    """Dictionary entry response."""
    word: str
    readings: List[DictionaryReadingSchema]


class PrefixSearchResponseSchema(BaseModel):
    """Prefix search response."""
    entries: List[DictionaryEntrySchema]
    count: int


class KanjiEntrySchema(BaseModel):
    """Kanji entry response."""
    kanji: str
    reading: str
    meanings: str
    strokes: int
    radical: str
    penstrokes: str
    shape: str
    unicode: str


class WordLookupRequest(BaseModel):
    """Word lookup request."""
    word: str = Field(..., min_length=1, max_length=100, description="Word to look up")


class PrefixSearchRequest(BaseModel):
    """Prefix search request."""
    prefix: str = Field(..., min_length=1, max_length=50, description="Prefix to search for")
    limit: int = Field(default=100, ge=1, le=500, description="Maximum number of results")


class KanjiLookupRequest(BaseModel):
    """Kanji lookup request."""
    kanji: str = Field(..., min_length=1, max_length=1, description="Single kanji character to look up")