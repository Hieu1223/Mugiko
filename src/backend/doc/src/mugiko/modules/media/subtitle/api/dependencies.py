"""Subtitle API dependencies."""
from typing import AsyncGenerator
from mugiko.modules.media.subtitle.service.subtitle_service import SubtitleService
from mugiko.modules.media.subtitle.service.provider_service import ProviderService
from mugiko.modules.media.subtitle.persistent.repository import SubtitleRepository
from mugiko.modules.core.job.service.job_service import JobService
from mugiko.modules.core.job.persistent.repository import JobRepository
from mugiko.common.persistent.session import get_session_cm


async def get_subtitle_service() -> AsyncGenerator[SubtitleService, None]:
    """Create subtitle service with session."""
    async with get_session_cm() as session:
        repo = SubtitleRepository(session)
        job_repo = JobRepository(session)
        job_service = JobService(job_repo)
        yield SubtitleService(repo, job_service)


async def get_provider_service() -> AsyncGenerator[ProviderService, None]:
    """Create provider service with session."""
    async with get_session_cm() as session:
        repo = SubtitleRepository(session)
        yield ProviderService(repo)