"""YouTube URL utilities."""
import re
from typing import Optional


YOUTUBE_URL_PATTERNS = [
    # Standard YouTube URLs
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
    r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    r"(?:https?://)?(?:www\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})",
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
    # YouTube Music
    r"(?:https?://)?(?:www\.)?music\.youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
    # youtu.be short URLs
    r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})",
    # YouTube with additional params
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})",
]


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    for pattern in YOUTUBE_URL_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def normalize_youtube_url(url: str) -> str:
    """Normalize YouTube URL to standard watch format."""
    video_id = extract_video_id(url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube URL."""
    return extract_video_id(url) is not None