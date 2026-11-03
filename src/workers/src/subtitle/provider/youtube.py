"""YouTube subtitle provider.

Downloads a subtitle track with yt-dlp in YouTube's native ``json3`` format.
The provider only fetches; tokenization happens in the processor.
"""

import json
import logging
import os
import tempfile
import urllib.parse
from typing import Any, Dict, Optional

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from ..types import RawSubtitleArtifact
from .registry import provider, service

logger = logging.getLogger(__name__)


class NoSubtitlesAvailable(Exception):
    """The requested language has no subtitles for this video."""


def _video_id_from_url(url: str) -> str:
    """Best-effort YouTube video id extraction; falls back to the raw URL."""
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()

    if host in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("v"):
            return query["v"][0]
        parts = [part for part in parsed.path.split("/") if part]
        if parts and parts[0] in ("shorts", "live", "embed") and len(parts) > 1:
            return parts[1]

    if host == "youtu.be":
        parts = [part for part in parsed.path.split("/") if part]
        if parts:
            return parts[0]

    return url


def _pick_subtitle_file(tmp_dir: str, language: str) -> Optional[str]:
    files = sorted(
        filename
        for filename in os.listdir(tmp_dir)
        if filename.endswith(".json3")
    )
    if not files:
        return None

    for filename in files:
        if filename.endswith(f".{language}.json3"):
            return os.path.join(tmp_dir, filename)
    return os.path.join(tmp_dir, files[0])


@provider(
    name="YouTube",
    kind="youtube",
    base_url="https://www.youtube.com",
)
class YouTubeProvider:
    """Fetches subtitles with yt-dlp and returns the raw json3 document."""

    def _download_json3(self, url: str, language: str) -> RawSubtitleArtifact:
        video_id = _video_id_from_url(url)
        options: Dict[str, Any] = {
            "skip_download": True,  # subtitles only, never the media
            "writesubtitles": True,  # prefer manual subtitles
            "writeautomaticsub": True,  # fall back to auto captions
            "subtitleslangs": [language],
            "subtitlesformat": "json3/best",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            options["outtmpl"] = os.path.join(tmp_dir, "%(id)s.%(ext)s")
            try:
                with YoutubeDL(options) as ydl:
                    info = ydl.extract_info(url, download=True)
            except DownloadError as exc:
                raise NoSubtitlesAvailable(
                    f"Could not download '{language}' subtitles for {url}: {exc}"
                ) from exc

            if isinstance(info, dict) and info.get("id"):
                video_id = str(info["id"])

            path = _pick_subtitle_file(tmp_dir, language)
            if path is None:
                raise NoSubtitlesAvailable(
                    f"No '{language}' subtitles available for {url}"
                )

            with open(path, "r", encoding="utf-8") as file_handle:
                raw = json.load(file_handle)

        logger.info("Downloaded %s subtitle track for %s", language, video_id)
        return RawSubtitleArtifact(
            video_id=video_id,
            video_url=url,
            language=language,
            format="json3",
            raw=raw,
        )

    @service(
        "youtube_ja",
        "Download Japanese Subtitles",
        options={"language": "ja"},
    )
    def youtube_ja(self, url: str) -> RawSubtitleArtifact:
        """Download the Japanese subtitle track (auto fallback included)."""
        return self._download_json3(url, "ja")
