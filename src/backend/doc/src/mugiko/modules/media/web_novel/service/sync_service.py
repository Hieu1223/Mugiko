"""Sync service for web novel module."""
from typing import Optional
from uuid import UUID
import asyncio

from mugiko.modules.media.web_novel.provider.syosetsu import SyosetsuProvider
from mugiko.modules.media.web_novel.service.tokenizer import get_tokenizer
from mugiko.modules.media.web_novel.persistent.repository import NovelRepository, ChapterRepository, ParagraphRepository
from mugiko.modules.core.job.persistent.repository import JobRepository
from mugiko.modules.core.job.persistent.models import JobStatus, JobType
from mugiko.modules.media.web_novel.exceptions.web_novel_exceptions import ProviderError, SyncError
from mugiko.common.persistent.session import async_session_maker


class SyncService:
    """Service for orchestrating initial novel sync."""
    
    def __init__(self, delay_seconds: float = 1.0):
        self.delay_seconds = delay_seconds
    
    async def run_initial_sync(self, novel_id: UUID, job_id: UUID) -> None:
        """Run initial sync for a novel in background."""
        async with async_session_maker() as session:
            novel_repo = NovelRepository(session)
            chapter_repo = ChapterRepository(session)
            paragraph_repo = ParagraphRepository(session)
            job_repo = JobRepository(session)
            
            # Update job to running
            await job_repo.update_job_status(job_id, JobStatus.RUNNING)
            await session.commit()
            
            try:
                # Get novel
                novel = await novel_repo.get_by_id(novel_id)
                if not novel:
                    raise SyncError(f"Novel not found: {novel_id}")
                
                # Initialize provider and tokenizer
                async with SyosetsuProvider(delay_seconds=self.delay_seconds) as provider:
                    tokenizer = get_tokenizer()
                    
                    # Fetch chapter list
                    chapters = await provider.fetch_chapter_list(novel.source_id)
                    
                    # Process each chapter
                    for chapter_info in chapters:
                        # Fetch chapter content
                        content = await provider.fetch_chapter_content(chapter_info.url)
                        
                        # Split into paragraphs
                        paragraphs = self._split_paragraphs(content.text)
                        
                        # Tokenize paragraphs
                        tokenized_paragraphs = []
                        for idx, para_text in enumerate(paragraphs):
                            words = tokenizer.tokenize_to_dict(para_text)
                            tokenized_paragraphs.append({
                                'idx': idx + 1,
                                'text': para_text,
                                'words': words,
                            })
                        
                        # Create chapter
                        chapter = await chapter_repo.create(
                            novel_id=novel_id,
                            idx=chapter_info.idx,
                            title=chapter_info.title or content.title,
                        )
                        
                        # Create paragraphs
                        await paragraph_repo.create_batch(chapter.id, tokenized_paragraphs)
                        
                        # Commit per chapter
                        await session.commit()
                
                # Mark job completed
                await job_repo.update_job_status(job_id, JobStatus.COMPLETED)
                await session.commit()
                
            except Exception as e:
                # Mark job failed
                await job_repo.update_job_status(job_id, JobStatus.FAILED, error=str(e))
                await session.commit()
                raise SyncError(f"Sync failed: {str(e)}")
    
    def _split_paragraphs(self, text: str) -> list:
            """Split chapter text into segments of 2-3 sentences each."""
            if not text:
                return []
        
            # Split by sentence endings (Japanese and English)
            import re
            # Match sentence endings: 。 ！ ？ . ! ? followed by whitespace or end
            sentences = re.split(r'(?<=[。！？.!?])\s*', text)
            sentences = [s.strip() for s in sentences if s.strip()]
        
            # Group into segments of 2-3 sentences
            segments = []
            i = 0
            while i < len(sentences):
                # Randomly choose 2 or 3 sentences per segment
                segment_size = 2 if i + 2 >= len(sentences) else (2 if (i + 3 >= len(sentences) or len(sentences) - i == 3) else 3)
                # Actually, let's do: if remaining >= 3, use 3; if remaining == 2, use 2
                if len(sentences) - i >= 3:
                    segment_size = 3
                else:
                    segment_size = len(sentences) - i
            
                segment = ' '.join(sentences[i:i + segment_size])
                if segment:
                    segments.append(segment)
                i += segment_size
        
            return segments


async def run_sync_background(novel_id: UUID, job_id: UUID, delay_seconds: float = 1.0):
    """Background task entry point for running sync."""
    print(f"[DEBUG] run_sync_background called for novel_id={novel_id}, job_id={job_id}")
    service = SyncService(delay_seconds=delay_seconds)
    try:
        await service.run_initial_sync(novel_id, job_id)
        print(f"[DEBUG] run_sync_background completed for novel_id={novel_id}")
    except Exception as e:
        print(f"[ERROR] run_sync_background failed for novel_id={novel_id}: {e}")
        raise