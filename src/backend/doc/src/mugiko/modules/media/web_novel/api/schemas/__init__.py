"""API schemas package."""
from mugiko.modules.media.web_novel.api.schemas.novel import *

__all__ = [
    "SourceEnum",
    "WordToken",
    "ParagraphResponse",
    "ChapterResponse",
    "NovelResponse",
    "NovelWithChaptersResponse",
    "PreviewRequest",
    "PreviewResponse",
    "AddNovelRequest",
    "AddNovelResponse",
    "PaginatedNovelsResponse",
]