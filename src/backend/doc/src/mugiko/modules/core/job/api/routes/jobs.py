"""Job API routes."""
from fastapi import APIRouter, Depends
from uuid import UUID

from mugiko.modules.core.job.api.schema import JobResponse
from mugiko.modules.core.job.api.dependencies import get_job_service
from mugiko.modules.core.job.service.job_service import JobService
from mugiko.modules.core.user_management.api.dependencies import require_user
from mugiko.modules.core.user_management.service.dtos import AuthContext


router = APIRouter(prefix="/jobs", tags=["job"])


@router.get(
    "/{job_id}",
    response_model=JobResponse,
)
async def get_job(
    job_id: UUID,
    service: JobService = Depends(get_job_service),
    auth: AuthContext = Depends(require_user),
):
    """Get job status (creator or admin)."""
    job = await service.get_job(job_id)
    return job