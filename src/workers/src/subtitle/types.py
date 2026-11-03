"""Shared type contracts for the subtitle module."""

from typing import Any, Dict, List, TypedDict


class JobMessage(TypedDict):
    """One message on the subtitle Redis stream (see doc/stream_res.txt).

    ``id`` is the ``subtitles.id`` row created by the backend before the job
    is published (status ``queued``).
    """

    id: str
    service: str
    video_url: str
    provider: str


class CueWord(TypedDict):
    """A tokenized word: exactly two fields, as required by the schema."""

    surface: str
    hiragana: str


class SubtitleSegment(TypedDict):
    """One row for the ``subtitle_segments`` table."""

    idx: int
    start_ms: int
    end_ms: int
    words: List[CueWord]


class RawSubtitleArtifact(TypedDict):
    """Provider output handed to the processor."""

    video_id: str
    video_url: str
    language: str
    format: str
    raw: Dict[str, Any]
