"""Job service for managing background jobs."""
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from mugiko.modules.core.job.service.dtos import (
    JobCreate,
    JobResponse,
    JobType,
    JobStatus,
)
from mugiko.modules.core.job.persistent.repository import JobRepository
from mugiko.modules.core.job.exceptions import JobNotFoundError


class JobService:
    """Service for managing jobs."""

    def __init__(self, repo: JobRepository):
        self.repo = repo

    def _to_response(self, job) -> JobResponse:
        """Convert SQLAlchemy Job model to JobResponse DTO."""
        return JobResponse(
            job_id=job.job_id,
            job_type=JobType(job.job_type.value) if hasattr(job.job_type, 'value') else JobType(job.job_type),
            status=JobStatus(job.status.value) if hasattr(job.status, 'value') else JobStatus(job.status),
            ref_type=job.ref_type,
            ref_id=job.ref_id,
            error=job.error,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )

    async def create_job(self, data: JobCreate) -> JobResponse:
        """Create a new job."""
        job = await self.repo.create_job(
            job_type=data.job_type,
            ref_type=data.ref_type,
            ref_id=data.ref_id,
        )
        # Manually construct to avoid greenlet issues with lazy loading
        return self._to_response(job)

    async def get_job(self, job_id: UUID) -> JobResponse:
        """Get a job by ID."""
        job = await self.repo.get_job(job_id)
        if not job:
            raise JobNotFoundError()
        return self._to_response(job)

    async def get_jobs_by_ref(self, ref_type: str, ref_id: UUID) -> List[JobResponse]:
        """Get jobs by reference."""
        jobs = await self.repo.get_jobs_by_ref(ref_type, ref_id)
        return [self._to_response(j) for j in jobs]

    async def update_job_status(
        self, job_id: UUID, status: JobStatus, error: Optional[str] = None
    ) -> JobResponse:
        """Update job status."""
        job = await self.repo.update_job_status(job_id, status, error)
        if not job:
            raise JobNotFoundError()
        return self._to_response(job)