"""YouTube subtitle provider using yt-dlp."""
import os
import json
import subprocess
import tempfile
from typing import List, Optional
from pathlib import Path

from mugiko.modules.media.subtitle.provider.base import SubtitleProvider
from mugiko.modules.media.subtitle.provider.dtos import (
    ProviderSyncDTO,
    ProviderServiceDTO,
    SubtitleResultDTO,
    SubtitleSegmentProviderDTO,
    SubtitleWordDTO,
)
from mugiko.common.utils.youtube import extract_video_id, normalize_youtube_url
from mugiko.modules.media.subtitle.service.tokenizer import tokenize_text


class YouTubeSubtitleProvider(SubtitleProvider):
    """YouTube subtitle provider using yt-dlp."""

    def __init__(self):
        self.provider_name = "YouTube"
        self.provider_kind = "youtube"
        # Single built-in service for manual Japanese captions
        self.services = [
            ProviderServiceDTO(
                service_key="youtube-manual-ja",
                name="YouTube Manual Japanese Captions",
                options={"caption_type": "manual", "language": "ja"},
            ),
            ProviderServiceDTO(
                service_key="youtube-auto-ja",
                name="YouTube Auto-generated Japanese Captions",
                options={"caption_type": "auto", "language": "ja"},
            ),
        ]

    async def sync(self) -> ProviderSyncDTO:
        """Return provider info and available services."""
        return ProviderSyncDTO(
            provider_name=self.provider_name,
            provider_kind=self.provider_kind,
            services=self.services,
        )

    async def get_subtitle(self, video_url: str, service_key: str) -> SubtitleResultDTO:
        """Download Japanese subtitle from YouTube using yt-dlp."""
        video_id = extract_video_id(video_url)
        normalized_url = normalize_youtube_url(video_url)

        # Find the service config
        service = next((s for s in self.services if s.service_key == service_key), None)
        if not service:
            raise ValueError(f"Service {service_key} not found")

        caption_type = service.options.get("caption_type", "manual")
        language = service.options.get("language", "ja")

        # Get cookies from environment
        cookies_file = self._get_cookies_file()

        # Try to download subtitles
        subtitle_data = await self._download_subtitle(
            video_id, normalized_url, caption_type, language, cookies_file
        )
        print(subtitle_data)

        if not subtitle_data:
            raise ValueError(f"No {language} subtitles found for video {video_id}")

        return subtitle_data

    def _get_cookies_file(self) -> Optional[str]:
        """Get cookies file path from environment variable."""
        cookies_env = os.environ.get("YOUTUBE_COOKIES")
        if not cookies_env:
            return None

        # Write cookies to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(cookies_env)
            return f.name

    async def _download_subtitle(
        self,
        video_id: str,
        video_url: str,
        caption_type: str,
        language: str,
        cookies_file: Optional[str],
    ) -> Optional[SubtitleResultDTO]:
        """Download subtitle using yt-dlp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_template = os.path.join(tmpdir, "subtitle")

            # Build yt-dlp command
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--write-subs",
                "--write-auto-subs",
                "--sub-lang",
                language,
                "--sub-format",
                "json3",  # JSON3 format includes word timestamps
                "-o",
                output_template,
            ]

            if cookies_file:
                cmd.extend(["--cookies", cookies_file])

            # Prefer manual captions first, then auto
            if caption_type == "manual":
                cmd.extend(["--sub-format", "json3"])
            # For auto captions, yt-dlp will try auto if manual not found

            cmd.append(video_url)

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except subprocess.TimeoutExpired:
                raise ValueError("Subtitle download timed out")
            except FileNotFoundError:
                raise ValueError("yt-dlp not installed. Please install yt-dlp.")

            if result.returncode != 0:
                # Check if it's because no subtitles available
                if "no subtitles" in result.stderr.lower() or "unavailable" in result.stderr.lower():
                    return None
                raise ValueError(f"yt-dlp error: {result.stderr}")

            # Find the downloaded subtitle file
            subtitle_files = list(Path(tmpdir).glob("*.json3")) + list(Path(tmpdir).glob("*.vtt"))
            if not subtitle_files:
                # Try to find any subtitle file
                subtitle_files = list(Path(tmpdir).glob("*." + language + ".*"))
                if not subtitle_files:
                    subtitle_files = list(Path(tmpdir).glob("*.ja.*"))

            if not subtitle_files:
                return None

            # Parse the subtitle file
            subtitle_file = subtitle_files[0]
            return self._parse_subtitle_file(subtitle_file, video_id, video_url)

    def _parse_subtitle_file(
        self, subtitle_file: Path, video_id: str, video_url: str
    ) -> Optional[SubtitleResultDTO]:
        """Parse subtitle file (json3 or vtt) into segments."""
        if subtitle_file.suffix == ".json3":
            return self._parse_json3(subtitle_file, video_id, video_url)
        elif subtitle_file.suffix == ".vtt":
            return self._parse_vtt(subtitle_file, video_id, video_url)
        return None

    def _parse_json3(
        self, subtitle_file: Path, video_id: str, video_url: str
    ) -> SubtitleResultDTO:
        """Parse YouTube json3 subtitle format."""
        with open(subtitle_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        segments = []
        for idx, event in enumerate(data.get("events", [])):
            if "segs" not in event:
                continue

            start_ms = event.get("tStartMs", 0)
            duration_ms = event.get("dDurationMs", 0)
            end_ms = start_ms + duration_ms

            # Build full text from all segments
            full_text_parts = []
            has_word_timing = False
            
            for seg in event["segs"]:
                if "utf8" in seg:
                    text = seg["utf8"]
                    full_text_parts.append(text)
                    # Check if this segment has word-level timing
                    if seg.get("tOffsetMs") is not None:
                        has_word_timing = True

            if not full_text_parts:
                continue
                
            full_text = "".join(full_text_parts)
            
            words = []
            
            if has_word_timing:
                # Use existing word-level timing logic
                for seg in event["segs"]:
                    if "utf8" in seg:
                        text = seg["utf8"]
                        word_start = seg.get("tOffsetMs")
                        if word_start is not None:
                            words.append(
                                SubtitleWordDTO(
                                    text=text,
                                    start_ms=start_ms + word_start,
                                    end_ms=start_ms
                                    + word_start
                                    + seg.get("dDurationMs", duration_ms),
                                )
                            )
                        else:
                            words.append(SubtitleWordDTO(text=text))
            else:
                # No word-level timing - tokenize the full text into individual words
                tokenized = tokenize_text(full_text)
                # Distribute segment timing evenly across tokens (approximate)
                token_count = len(tokenized)
                if token_count > 0:
                    token_duration = duration_ms // token_count
                    for token_idx, token in enumerate(tokenized):
                        token_start = start_ms + (token_idx * token_duration)
                        token_end = start_ms + ((token_idx + 1) * token_duration)
                        words.append(
                            SubtitleWordDTO(
                                text=token["surface"],
                                start_ms=token_start,
                                end_ms=token_end,
                                hiragana=token["reading"],
                            )
                        )
                else:
                    # Fallback: single word with full text
                    words.append(SubtitleWordDTO(text=full_text))

            # For word-timed segments, add hiragana readings
            if has_word_timing and words:
                tokenized = tokenize_text(full_text)
                reading_map = {t["surface"]: t["reading"] for t in tokenized}
                for word in words:
                    if word.text in reading_map:
                        word.hiragana = reading_map[word.text]
                    else:
                        for token_surface, token_reading in reading_map.items():
                            if token_surface in word.text or word.text in token_surface:
                                word.hiragana = token_reading
                                break

            segments.append(
                SubtitleSegmentProviderDTO(
                    idx=idx,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    words=words if words else None,
                )
            )

        return SubtitleResultDTO(
            video_id=video_id,
            video_url=video_url,
            segments=segments,
        )

    def _parse_vtt(
        self, subtitle_file: Path, video_id: str, video_url: str
    ) -> SubtitleResultDTO:
        """Parse VTT subtitle format (fallback)."""
        import re

        segments = []
        with open(subtitle_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Simple VTT parsing
        # Format: HH:MM:SS.mmm --> HH:MM:SS.mmm
        pattern = re.compile(
            r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\s*\n([^\n]+)"
        )

        for idx, match in enumerate(pattern.finditer(content)):
            start_str, end_str, text = match.groups()
            start_ms = self._time_to_ms(start_str)
            end_ms = self._time_to_ms(end_str)

            # Tokenize the text into individual words
            tokenized = tokenize_text(text.strip())
            words = []
            token_count = len(tokenized)
            duration_ms = end_ms - start_ms
            
            if token_count > 0:
                token_duration = duration_ms // token_count
                for token_idx, token in enumerate(tokenized):
                    token_start = start_ms + (token_idx * token_duration)
                    token_end = start_ms + ((token_idx + 1) * token_duration)
                    words.append(
                        SubtitleWordDTO(
                            text=token["surface"],
                            start_ms=token_start,
                            end_ms=token_end,
                            hiragana=token["reading"],
                        )
                    )
            else:
                # Fallback: single word with full text
                words.append(SubtitleWordDTO(text=text.strip()))

            segments.append(
                SubtitleSegmentProviderDTO(
                    idx=idx,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    words=words,
                )
            )

        return SubtitleResultDTO(
            video_id=video_id,
            video_url=video_url,
            segments=segments,
        )

    def _time_to_ms(self, time_str: str) -> int:
        """Convert HH:MM:SS.mmm to milliseconds."""
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds_ms = parts[2].split(".")
        seconds = int(seconds_ms[0])
        milliseconds = int(seconds_ms[1]) if len(seconds_ms) > 1 else 0
        return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds