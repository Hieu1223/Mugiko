"""YouTube subtitle provider.

Downloads a subtitle track with yt-dlp in YouTube's native ``json3`` format.
The provider only fetches; tokenization happens in the processor.
"""

import json
import logging
import os
import shutil
import tempfile
import time
import urllib.parse
from typing import Any, Dict, List, Optional

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from ..types import RawSubtitleArtifact
from .registry import provider, service

logger = logging.getLogger(__name__)

_MAX_DOWNLOAD_ATTEMPTS = 4
_RETRY_BACKOFF_BASE_SECONDS = 2

# Transient YouTube/yt-dlp errors worth retrying with backoff.
_RETRYABLE_ERROR_MARKERS = (
    "http error 429",
    "too many requests",
    "http error 500",
    "http error 502",
    "http error 503",
    "http error 504",
    "temporary failure",
    "connection reset",
    "timeout",
)


def _is_retryable_download_error(exc: DownloadError) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _RETRYABLE_ERROR_MARKERS)


# Path to a Netscape-format cookies.txt used by yt-dlp to authenticate with
# YouTube (helps avoid HTTP 429 rate limits on subtitle downloads).
# Set via the YTDLP_COOKIES_FILE environment variable; defaults to /app/cookies.txt.
def _cookies_file() -> Optional[str]:
    return os.getenv("YTDLP_COOKIES_FILE", "/app/cookies.txt")


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
        if filename.endswith((".json3", ".vtt", ".srt", ".ttml"))
    )
    if not files:
        return None

    # Prefer json3 (word-level timing), then any available subtitle format.
    for ext in (".json3", ".vtt", ".srt", ".ttml"):
        for filename in files:
            if filename.endswith(f".{language}.{ext}"):
                return os.path.join(tmp_dir, filename)
        for filename in files:
            if filename.endswith(ext):
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

        def build_options(fmt: Optional[str]) -> Dict[str, Any]:
            options: Dict[str, Any] = {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [language],
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
                "retries": 10,
                "fragment_retries": 10,
                # EJS challenge solver — remote components fetched from GitHub
                "remote_components": ["ejs:github"],
            }
            if fmt:
                options["subtitlesformat"] = fmt
            return options

        cookies_file = _cookies_file()
        if cookies_file and os.path.exists(cookies_file):
            writable_cookies = os.path.join(tempfile.gettempdir(), "youtube_cookies.txt")
            try:
                shutil.copyfile(cookies_file, writable_cookies)
                logger.info(
                    "Using cookies file for YouTube download: %s (from %s)",
                    writable_cookies,
                    cookies_file,
                )
            except OSError:
                logger.warning(
                    "Could not copy cookies file %s — proceeding without cookies",
                    cookies_file,
                )
                writable_cookies = None
        else:
            writable_cookies = None

        last_error: Optional[Exception] = None
        raw: Optional[Dict[str, Any]] = None
        subtitle_path: Optional[str] = None

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Try json3 first (word-level timing), then fall back to any format.
            for fmt in ("json3", None):
                opts = build_options(fmt)
                opts["outtmpl"] = os.path.join(tmp_dir, "%(id)s.%(ext)s")
                if writable_cookies:
                    opts["cookiefile"] = writable_cookies

                try:
                    with YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                    break
                except DownloadError as exc:
                    last_error = exc
                    msg = str(exc).lower()
                    if fmt == "json3" and (
                        "format is not available" in msg
                        or "requested format" in msg
                    ):
                        logger.warning(
                            "json3 subtitles not available for %s, "
                            "falling back to best subtitle format",
                            url,
                        )
                        continue
                    raise NoSubtitlesAvailable(
                        f"Could not download '{language}' subtitles for {url}: {exc}"
                    ) from exc

            if isinstance(info, dict) and info.get("id"):
                video_id = str(info["id"])

            subtitle_path = _pick_subtitle_file(tmp_dir, language)
            if subtitle_path is None:
                raise NoSubtitlesAvailable(
                    f"No '{language}' subtitles available for {url}"
                )

            raw = self._parse_subtitle_file(subtitle_path)

        logger.info("Downloaded %s subtitle track for %s", language, video_id)
        return RawSubtitleArtifact(
            video_id=video_id,
            video_url=url,
            language=language,
            format="json3",
            raw=raw,
        )

    def _parse_subtitle_file(self, path: str) -> Dict[str, Any]:
        """Parse a subtitle file into a json3-compatible dict.

        json3 files are passed through as-is. VTT/SRT files are converted to
        the json3 ``events`` structure so the existing processor can handle them.
        """
        ext = os.path.splitext(path)[1].lower()
        if ext == ".json3":
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        if ext == ".vtt":
            return self._vtt_to_json3(path)

        if ext == ".srt":
            return self._srt_to_json3(path)

        # Unknown format: try JSON anyway, fall back to empty.
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {"events": []}

    def _vtt_to_json3(self, path: str) -> Dict[str, Any]:
        """Convert a WebVTT file to a json3-compatible dict."""
        import re

        events: List[Dict[str, Any]] = []
        timestamp_re = re.compile(
            r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})"
        )

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            m = timestamp_re.search(line)
            if m:
                start_ms = self._vtt_timestamp_to_ms(m.group(1))
                end_ms = self._vtt_timestamp_to_ms(m.group(2))
                i += 1
                text_parts: List[str] = []
                while i < len(lines) and lines[i].strip():
                    text_parts.append(lines[i].strip())
                    i += 1
                text = " ".join(text_parts).replace("\n", " ").strip()
                if text:
                    events.append(
                        {
                            "tStartMs": start_ms,
                            "dDurationMs": max(0, end_ms - start_ms),
                            "segs": [{"utf8": text}],
                        }
                    )
            else:
                i += 1

        return {"events": events}

    def _srt_to_json3(self, path: str) -> Dict[str, Any]:
        """Convert an SRT file to a json3-compatible dict."""
        import re

        events: List[Dict[str, Any]] = []
        timestamp_re = re.compile(
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
        )

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        blocks = re.split(r"\n\s*\n", content.strip())
        for block in blocks:
            lines = block.splitlines()
            if len(lines) < 2:
                continue
            m = timestamp_re.search(lines[1])
            if not m:
                continue
            start_ms = (
                int(m.group(1)) * 3600000
                + int(m.group(2)) * 60000
                + int(m.group(3)) * 1000
                + int(m.group(4))
            )
            end_ms = (
                int(m.group(5)) * 3600000
                + int(m.group(6)) * 60000
                + int(m.group(7)) * 1000
                + int(m.group(8))
            )
            text = " ".join(lines[2:]).strip()
            if text:
                events.append(
                    {
                        "tStartMs": start_ms,
                        "dDurationMs": max(0, end_ms - start_ms),
                        "segs": [{"utf8": text}],
                    }
                )

        return {"events": events}

    def _vtt_timestamp_to_ms(self, ts: str) -> int:
        parts = ts.split(":")
        return (
            int(parts[0]) * 3600000
            + int(parts[1]) * 60000
            + int(parts[2].split(".")[0]) * 1000
            + int(parts[2].split(".")[1])
        )

    @service(
        "youtube_ja",
        "Download Japanese Subtitles",
        options={"language": "ja"},
    )
    def youtube_ja(self, url: str) -> RawSubtitleArtifact:
        """Download the Japanese subtitle track (auto fallback included)."""
        return self._download_json3(url, "ja")

    @service(
        "youtube_vi",
        "Download Vietnamese Subtitles",
        options={"language": "vi"},
    )
    def youtube_vi(self, url: str) -> RawSubtitleArtifact:
        """Download the Vietnamese subtitle track (auto fallback included)."""
        return self._download_json3(url, "vi")
