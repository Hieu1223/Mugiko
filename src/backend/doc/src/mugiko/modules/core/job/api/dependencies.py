"""Job API dependencies."""
from typing import AsyncGenerator
from mugiko.modules.core.job.service.job_service import JobService
from mugiko.modules.core.job.persistent.repository import JobRepository
from mugiko.common.persistent.session import get_session_cm


async def get_job_service() -> AsyncGenerator[JobService, None]:
    """Create job service with session."""
    async with get_session_cm() as session:
        job_repo = JobRepository(session)
        yield JobService(job_repo)