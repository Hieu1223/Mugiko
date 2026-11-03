"""Job repository for data access."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from mugiko.modules.core.job.persistent.models import Job, JobStatus, JobType


class JobRepository:
    """Repository for job module data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_job(
        self,
        job_type: JobType,
        ref_type: str,
        ref_id: UUID,
    ) -> Job:
        job = Job(
            job_type=job_type,
            ref_type=ref_type,
            ref_id=ref_id,
            status=JobStatus.PENDING,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(self, job_id: UUID) -> Optional[Job]:
        result = await self.session.execute(
            select(Job).where(Job.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def get_jobs_by_ref(self, ref_type: str, ref_id: UUID) -> List[Job]:
        result = await self.session.execute(
            select(Job)
            .where(Job.ref_type == ref_type, Job.ref_id == ref_id)
            .order_by(Job.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_job_status(
        self, job_id: UUID, status: JobStatus, error: Optional[str] = None
    ) -> Optional[Job]:
        job = await self.get_job(job_id)
        if job:
            job.status = status
            if error:
                job.error = error
            if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                from datetime import datetime, timezone
                job.completed_at = datetime.now(timezone.utc)
            await self.session.flush()
            # Refresh to get the updated values
            await self.session.refresh(job)
        return job