"""Persistent layer package."""
from mugiko.modules.media.web_novel.persistent.models import Novel, Chapter, Paragraph, SourceEnum
from mugiko.modules.media.web_novel.persistent.dtos import *
from mugiko.modules.media.web_novel.persistent.repository import NovelRepository, ChapterRepository, ParagraphRepository

__all__ = [
    "Novel",
    "Chapter",
    "Paragraph",
    "SourceEnum",
    "NovelRepository",
    "ChapterRepository",
    "ParagraphRepository",
]