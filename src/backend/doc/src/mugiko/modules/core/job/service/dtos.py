"""Job service DTOs."""
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime
from enum import Enum


class JobType(str, Enum):
    SUBTITLE_GENERATION = "subtitle_generation"
    NOVEL_SYNC = "novel_sync"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobCreate(BaseModel):
    job_type: JobType
    ref_type: str
    ref_id: UUID


class JobResponse(BaseModel):
    job_id: UUID
    job_type: JobType
    status: JobStatus
    ref_type: str
    ref_id: UUID
    error: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True