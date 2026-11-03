"""Convert yt-dlp ``json3`` documents into ``subtitle_segments`` rows.

Pure transform: no I/O and no imports from the stream/persistence layers.
Japanese cues are tokenized with Janome and stored as ``{surface, hiragana}``;
other languages keep the full cue as one token so no text is lost.
"""

import logging
from typing import Any, Dict, List, Optional

from janome.tokenizer import Tokenizer

from ..types import CueWord, SubtitleSegment

logger = logging.getLogger(__name__)

_tokenizer: Optional[Tokenizer] = None


def _get_tokenizer() -> Tokenizer:
    """Lazily create one tokenizer per process (dictionary load is slow)."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = Tokenizer()
    return _tokenizer


def _katakana_to_hiragana(text: str) -> str:
    """Shift katakana codepoints to their hiragana counterparts."""
    converted = []
    for character in text:
        codepoint = ord(character)
        if 0x30A1 <= codepoint <= 0x30F6:
            converted.append(chr(codepoint - 0x60))
        else:
            converted.append(character)
    return "".join(converted)


def _has_kana(text: str) -> bool:
    return any(0x3040 <= ord(character) <= 0x30FF for character in text)


def _tokenize_japanese(text: str) -> List[CueWord]:
    words: List[CueWord] = []
    for token in _get_tokenizer().tokenize(text):
        surface = token.surface
        if not surface.strip():
            continue
        reading = getattr(token, "reading", "") or ""
        if not _has_kana(reading):
            reading = surface  # dictionary miss — keep the written form
        words.append(
            CueWord(
                surface=surface,
                hiragana=_katakana_to_hiragana(reading),
            )
        )
    return words


def _plain_words(text: str) -> List[CueWord]:
    """Non-Japanese fallback: keep the whole cue as one display token."""
    if not text:
        return []
    return [CueWord(surface=text, hiragana="")]


def _cue_text(event: Dict[str, Any]) -> str:
    raw = "".join(
        segment.get("utf8", "") for segment in (event.get("segs") or [])
    )
    return raw.replace("\n", "").strip()


def json3_to_segments(
    raw: Dict[str, Any],
    language: str = "ja",
) -> List[SubtitleSegment]:
    """Convert a parsed json3 document into ordered, tokenized segment rows."""
    use_janome = language.split("-")[0].lower() == "ja"
    segments: List[SubtitleSegment] = []
    idx = 0

    for event in raw.get("events", []):
        if not isinstance(event, dict):
            continue

        text = _cue_text(event)
        if not text:
            continue

        words = _tokenize_japanese(text) if use_janome else _plain_words(text)
        if not words:
            continue

        try:
            start_ms = int(event["tStartMs"])
        except (KeyError, TypeError, ValueError):
            continue

        try:
            duration_ms = int(event.get("dDurationMs") or 0)
        except (TypeError, ValueError):
            duration_ms = 0

        segments.append(
            SubtitleSegment(
                idx=idx,
                start_ms=start_ms,
                end_ms=start_ms + duration_ms,
                words=words,
            )
        )
        idx += 1

    return segments
