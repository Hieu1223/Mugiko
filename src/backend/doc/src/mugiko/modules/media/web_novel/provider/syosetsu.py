"""Syosetsu provider for web novel module."""
import re
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import httpx
from bs4 import BeautifulSoup


@dataclass
class NovelMetadata:
    source_id: str
    title: str
    author: Optional[str]
    synopsis: Optional[str]
    chapter_count: int
    is_short_story: bool


@dataclass
class ChapterInfo:
    idx: int
    title: Optional[str]
    url: str


@dataclass
class ChapterContent:
    title: Optional[str]
    text: str


class SyosetsuProvider:
    """Provider for Syosetsu (Shousetsuka ni Narou) web novels."""
    
    BASE_URL = "https://ncode.syosetu.com"
    USER_AGENT = "Mozilla/5.0 (compatible; Mugiko/1.0)"
    
    # URL patterns
    NOVEL_URL_PATTERN = re.compile(
        r'https?://ncode\.syosetu\.com/(n\d+[a-z]*)(?:/)?'
    )
    CHAPTER_URL_PATTERN = re.compile(
        r'https?://ncode\.syosetu\.com/(n\d+[a-z]*)/(\d+)/?'
    )
    
    def __init__(self, delay_seconds: float = 1.0):
        self.delay_seconds = delay_seconds
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure the HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": self.USER_AGENT},
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client
    
    async def __aenter__(self) -> "SyosetsuProvider":
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def close(self) -> None:
        """Explicitly close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def validate_url(self, url: str) -> Optional[str]:
        """Validate Syosetsu URL and extract novel code."""
        match = self.NOVEL_URL_PATTERN.match(url.strip())
        if match:
            return match.group(1)
        return None
    
    def extract_novel_code(self, url: str) -> Optional[str]:
        """Extract novel code from URL."""
        return self.validate_url(url)
    
    async def fetch_metadata(self, novel_code: str) -> NovelMetadata:
            """Fetch novel metadata from Syosetsu."""
            url = f"{self.BASE_URL}/{novel_code}/"
            response = await self._client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Title - new site uses p-novel__title
            title_elem = soup.select_one('.p-novel__title') or soup.select_one('.novel_title')
            title = title_elem.get_text(strip=True) if title_elem else "Unknown"

            # Author - new site uses p-novel__author
            author_elem = soup.select_one('.p-novel__author a') or soup.select_one('.novel_writername a')
            author = author_elem.get_text(strip=True) if author_elem else None

            # Synopsis - new site uses p-novel__summary
            synopsis_elem = soup.select_one('.p-novel__summary') or soup.select_one('#novel_ex')
            synopsis = synopsis_elem.get_text(strip=True) if synopsis_elem else None

            # Chapter list - new site uses p-eplist__chapter-title
            chapter_titles = soup.select('.p-eplist__chapter-title')
            is_short_story = len(chapter_titles) == 0
            chapter_count = len(chapter_titles) if not is_short_story else 1

            return NovelMetadata(
                source_id=novel_code,
                title=title,
                author=author,
                synopsis=synopsis,
                chapter_count=chapter_count,
                is_short_story=is_short_story,
            )
    
    async def fetch_chapter_list(self, novel_code: str) -> List[ChapterInfo]:
            """Fetch list of chapters."""
            url = f"{self.BASE_URL}/{novel_code}/"
            response = await self._client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            chapters = []

            # Find chapter links - new site structure uses /ncode/1/ format links
            chapter_links = soup.select(f'a[href^="/{novel_code}/"]')
        
            # Filter to only chapter links (numeric paths like /n6316bn/1/, /n6316bn/2/)
            import re
            chapter_pattern = re.compile(f'/{re.escape(novel_code)}/(\\d+)/?$')
            filtered_links = []
            for link in chapter_links:
                href = link.get('href', '')
                match = chapter_pattern.match(href)
                if match:
                    filtered_links.append((int(match.group(1)), link))

            # Sort by chapter number
            filtered_links.sort(key=lambda x: x[0])

            if not filtered_links:
                # Short story - single chapter
                return [ChapterInfo(idx=1, title=None, url=f"{self.BASE_URL}/{novel_code}/")]

            for idx, (chapter_num, link) in enumerate(filtered_links, 1):
                href = link.get('href', '')
                chapter_url = f"{self.BASE_URL}{href}" if href.startswith('/') else href
                title = link.get_text(strip=True) or None
                chapters.append(ChapterInfo(idx=idx, title=title, url=chapter_url))

            return chapters
    
    async def fetch_chapter_content(self, chapter_url: str) -> ChapterContent:
            """Fetch chapter content and split into paragraphs."""
            await asyncio.sleep(self.delay_seconds)

            response = await self._client.get(chapter_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Title - new site uses p-novel__subtitle or h1
            title_elem = soup.select_one('.p-novel__subtitle') or soup.select_one('h1')
            title = title_elem.get_text(strip=True) if title_elem else None

            # Content - new site uses p-novel__body
            content_elem = soup.select_one('.p-novel__body') or soup.select_one('#novel_honbun')
            if not content_elem:
                return ChapterContent(title=title, text="")

            # Extract paragraphs from <p> tags
            p_tags = content_elem.select('p')
            paragraphs = [p.get_text(strip=True) for p in p_tags if p.get_text(strip=True)]
            text = '\n\n'.join(paragraphs)

            return ChapterContent(title=title, text=text)