"""Job module models."""
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from mugiko.common.persistent.session import Base


class JobType(str, enum.Enum):
    SUBTITLE_GENERATION = "subtitle_generation"
    NOVEL_SYNC = "novel_sync"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_type = Column(SQLEnum(JobType), nullable=False)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, nullable=False)
    ref_type = Column(String(50), nullable=False)
    ref_id = Column(PGUUID(as_uuid=True), nullable=False)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_jobs_ref", "ref_type", "ref_id"),
        Index("ix_jobs_status", "status"),
    )