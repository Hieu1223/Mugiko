"""Groq subtitle provider.

Generates subtitles from a video's audio using Groq's Whisper transcription API.
Downloads the audio track with yt-dlp, sends it to Groq, and converts the
transcription (with word/segment timestamps) into json3-compatible segments.
"""

import json
import logging
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

import requests
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from ..types import RawSubtitleArtifact
from .registry import provider, service

logger = logging.getLogger(__name__)

_GROQ_API_BASE = "https://api.groq.com/openai/v1"
_GROQ_TRANSCRIPTION_MODEL = "whisper-large-v3"
_MAX_DOWNLOAD_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 2


def _groq_api_key() -> Optional[str]:
    """Read the Groq API key from the file pointed to by GROQ_API_KEYS_FILE."""
    path = os.getenv("GROQ_API_KEYS_FILE", "/app/groq.txt")
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                key = line.strip()
                if key:
                    return key
    except OSError:
        pass
    return None


@provider(
    name="Groq",
    kind="groq",
    base_url="https://api.groq.com",
    auto_languages=["ja", "vi", "en"],
)
class GroqProvider:
    """Generates subtitles by transcribing video audio with Groq Whisper."""

    def generate(self, url: str, language: str) -> RawSubtitleArtifact:
        """Generate subtitles for the given language."""
        return self._generate(url, language)

    def _download_audio(self, url: str) -> Optional[str]:
        """Download audio from a video URL using yt-dlp. Returns path to audio file."""
        tmp_dir = tempfile.mkdtemp()
        try:
            options: Dict[str, Any] = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "128",
                    }
                ],
                "quiet": True,
                "no_warnings": True,
                "noprogress": True,
            }

            # Use cookies if available
            cookies_file = os.getenv("YTDLP_COOKIES_FILE", "/app/cookies.txt")
            if os.path.exists(cookies_file):
                writable_cookies = os.path.join(tempfile.gettempdir(), "groq_cookies.txt")
                try:
                    import shutil
                    shutil.copyfile(cookies_file, writable_cookies)
                    options["cookiefile"] = writable_cookies
                except OSError:
                    pass

            try:
                with YoutubeDL(options) as ydl:
                    info = ydl.extract_info(url, download=True)
            except DownloadError as exc:
                logger.warning("Failed to download audio for %s: %s", url, exc)
                return None

            # Find the downloaded audio file
            audio_path = None
            for filename in os.listdir(tmp_dir):
                if filename.endswith((".mp3", ".wav", ".m4a", ".ogg", ".webm")):
                    audio_path = os.path.join(tmp_dir, filename)
                    break

            if audio_path is None:
                files = os.listdir(tmp_dir)
                if files:
                    audio_path = os.path.join(tmp_dir, files[0])

            if audio_path is None:
                return None

            # Move audio out of temp dir so it survives cleanup
            persistent_path = os.path.join(tempfile.gettempdir(), os.path.basename(audio_path))
            import shutil
            shutil.move(audio_path, persistent_path)
            return persistent_path

        finally:
            # Clean up temp dir
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _transcribe(self, audio_path: str, language: str) -> Optional[Dict[str, Any]]:
        """Send audio to Groq Whisper API and return transcription with timestamps."""
        api_key = _groq_api_key()
        if not api_key:
            logger.error("No Groq API key found")
            return None

        for attempt in range(1, _MAX_DOWNLOAD_ATTEMPTS + 1):
            try:
                with open(audio_path, "rb") as audio_file:
                    response = requests.post(
                        f"{_GROQ_API_BASE}/audio/transcriptions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        files={"file": (os.path.basename(audio_path), audio_file)},
                        data={
                            "model": _GROQ_TRANSCRIPTION_MODEL,
                            "response_format": "verbose_json",
                            "language": language,
                        },
                        timeout=300,
                    )

                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < _MAX_DOWNLOAD_ATTEMPTS:
                        time.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                        continue
                    logger.warning(
                        "Groq API returned %d after %d attempts",
                        response.status_code,
                        _MAX_DOWNLOAD_ATTEMPTS,
                    )
                    return None

                if response.status_code >= 400:
                    logger.warning(
                        "Groq API error %d: %s",
                        response.status_code,
                        response.text[:500],
                    )
                    return None

                return response.json()

            except requests.RequestException as exc:
                if attempt < _MAX_DOWNLOAD_ATTEMPTS:
                    time.sleep(_RETRY_BACKOFF_SECONDS * attempt)
                    continue
                logger.warning("Groq API request failed: %s", exc)
                return None

        return None

    def _transcription_to_json3(
        self, transcription: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert Groq Whisper verbose_json response to json3-compatible dict."""
        events: List[Dict[str, Any]] = []

        segments = transcription.get("segments", [])
        for seg in segments:
            start_ms = int(seg.get("start", 0) * 1000)
            end_ms = int(seg.get("end", 0) * 1000)
            text = seg.get("text", "").strip()

            if not text:
                continue

            events.append(
                {
                    "tStartMs": start_ms,
                    "dDurationMs": max(0, end_ms - start_ms),
                    "segs": [{"utf8": text}],
                }
            )

        return {"events": events}

    def _generate(self, url: str, language: str) -> RawSubtitleArtifact:
        video_id = url.split("v=")[-1].split("&")[0] if "v=" in url else url

        audio_path = self._download_audio(url)
        if not audio_path:
            raise RuntimeError(f"Could not download audio for {url}")

        try:
            transcription = self._transcribe(audio_path, language)
            if not transcription:
                raise RuntimeError(f"Groq transcription failed for {url}")

            raw = self._transcription_to_json3(transcription)

            if not raw.get("events"):
                raise RuntimeError(f"No segments produced for {url}")

            return RawSubtitleArtifact(
                video_id=video_id,
                video_url=url,
                language=language,
                format="json3",
                raw=raw,
            )
        finally:
            # Clean up the audio file
            try:
                os.remove(audio_path)
            except OSError:
                pass

    # Services are auto-registered via auto_languages above.
