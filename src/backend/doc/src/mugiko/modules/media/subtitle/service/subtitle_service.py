"""Subtitle service for managing subtitles and generation."""
from typing import List, Optional
from uuid import UUID
import asyncio

from mugiko.modules.media.subtitle.service.dtos import (
    SubtitleCreate,
    SubtitleResponse,
    SubtitleListResponse,
    SubtitleSearchRequest,
    SubtitleSegmentResponse,
)
from mugiko.modules.media.subtitle.persistent.repository import SubtitleRepository
from mugiko.modules.media.subtitle.provider.factory import create_provider
from mugiko.modules.media.subtitle.provider.dtos import SubtitleResultDTO
from mugiko.modules.media.subtitle.exceptions import (
    SubtitleNotFoundError,
    SubtitleGenerationError,
    ProviderNotFoundError,
    ServiceNotFoundError,
    InvalidVideoURLError,
)
from mugiko.modules.media.subtitle.persistent.models import ProviderKind
from mugiko.common.utils.youtube import extract_video_id, normalize_youtube_url
from mugiko.modules.core.job.service.job_service import JobService
from mugiko.modules.core.job.service.dtos import JobCreate, JobType, JobStatus


class SubtitleService:
    """Service for managing subtitles and generation."""

    def __init__(self, repo: SubtitleRepository, job_service: JobService):
        self.repo = repo
        self.job_service = job_service

    async def create_subtitle(
        self,
        user_id: UUID,
        data: SubtitleCreate,
    ) -> SubtitleResponse:
        """Create a new subtitle and start generation job."""
        # Normalize video URL and extract video ID
        video_id = extract_video_id(data.video_url)
        if not video_id:
            raise InvalidVideoURLError()
        normalized_url = normalize_youtube_url(data.video_url)

        # Verify provider exists
        provider = await self.repo.get_provider(data.provider_id)
        if not provider:
            raise ProviderNotFoundError()

        # Verify service exists
        from sqlalchemy import select
        from mugiko.modules.media.subtitle.persistent.models import SubtitleProviderService
        result = await self.repo.session.execute(
            select(SubtitleProviderService).where(
                SubtitleProviderService.provider_id == data.provider_id,
                SubtitleProviderService.service_key == data.service_key,
                SubtitleProviderService.is_active == True,
            )
        )
        service = result.scalar_one_or_none()
        if not service:
            raise ServiceNotFoundError()

        # Create subtitle record
        subtitle = await self.repo.create_subtitle(
            video_id=video_id,
            video_url=normalized_url,
            provider_id=data.provider_id,
            service_id=service.id,
            created_by=user_id,
        )

        # Create job for generation
        job = await self.job_service.create_job(
            JobCreate(
                job_type=JobType.SUBTITLE_GENERATION,
                ref_type="subtitle",
                ref_id=subtitle.id,
            )
        )

        # Commit the session so the job is visible to the background task
        await self.repo.session.commit()

        # Start background generation
        # Note: In production, use a proper task queue like Celery or ARQ
        # For now, we'll run it as a background task
        asyncio.create_task(self._generate_subtitle(job.job_id, subtitle.id, normalized_url, data.service_key))

        # Manually construct response to avoid greenlet issues with lazy loading
        # Access attributes to get actual values (not Column objects)
        return SubtitleResponse(
            id=subtitle.id,
            video_id=subtitle.video_id,
            video_url=subtitle.video_url,
            provider_id=subtitle.provider_id,
            service_id=subtitle.service_id,
            created_by=subtitle.created_by,
            created_at=subtitle.created_at,
            segments=[],
        )

    async def _generate_subtitle(
        self,
        job_id: UUID,
        subtitle_id: UUID,
        video_url: str,
        service_key: str,
    ) -> None:
        """Background task to generate subtitle."""
        # Wait a bit for the main session to commit
        await asyncio.sleep(0.5)

        # Create a new session for the background task
        from mugiko.common.persistent.session import get_session_cm
        async with get_session_cm() as session:
            from mugiko.modules.media.subtitle.persistent.repository import SubtitleRepository
            from mugiko.modules.core.job.persistent.repository import JobRepository
            from mugiko.modules.core.job.service.job_service import JobService
            from mugiko.modules.core.job.exceptions import JobNotFoundError

            repo = SubtitleRepository(session)
            job_repo = JobRepository(session)
            job_service = JobService(job_repo)

            # Retry job lookup a few times in case session hasn't committed yet
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    job = await job_repo.get_job(job_id)
                    if job:
                        break
                except JobNotFoundError:
                    pass
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.2)
            else:
                # Job still not found after retries
                return

            try:
                await job_service.update_job_status(job_id, JobStatus.RUNNING)

                # Get provider info
                subtitle = await repo.get_subtitle(subtitle_id)
                if not subtitle:
                    raise SubtitleNotFoundError()

                provider = await repo.get_provider(subtitle.provider_id)
                if not provider:
                    raise ProviderNotFoundError()

                # Create provider instance
                config = {"base_url": provider.base_url} if provider.base_url else None
                provider_instance = create_provider(provider.kind.value, config)

                # Get subtitle from provider
                result: SubtitleResultDTO = await provider_instance.get_subtitle(video_url, service_key)

                # Store segments
                segments_data = [
                    {
                        "idx": seg.idx,
                        "start_ms": seg.start_ms,
                        "end_ms": seg.end_ms,
                        "words": [w.model_dump() for w in seg.words] if seg.words else None,
                    }
                    for seg in result.segments
                ]
                await repo.add_segments(subtitle_id, segments_data)

                # Update job as completed - manually construct response to avoid greenlet
                await job_repo.update_job_status(job_id, JobStatus.COMPLETED)
                # Don't call job_service.update_job_status as it triggers greenlet issues

            except Exception as e:
                try:
                    await job_repo.update_job_status(job_id, JobStatus.FAILED, error=str(e))
                except JobNotFoundError:
                    pass

    async def get_subtitle(self, subtitle_id: UUID, user_id: Optional[UUID] = None, limit: int = 100, offset: int = 0) -> SubtitleResponse:
            """Get a subtitle by ID, upserting access record if user provided."""
            subtitle = await self.repo.get_subtitle(subtitle_id)
            if not subtitle:
                raise SubtitleNotFoundError()

            # Upsert access record if user provided
            if user_id:
                await self.repo.upsert_access(user_id, subtitle_id)

            # Get paginated segments
            segments = await self.repo.get_segments(subtitle_id, limit=limit, offset=offset)

            # Manually construct response to avoid greenlet issues with lazy loading
            # Access attributes to get actual values (not Column objects)
            return SubtitleResponse(
                id=subtitle.id,
                video_id=subtitle.video_id,
                video_url=subtitle.video_url,
                provider_id=subtitle.provider_id,
                service_id=subtitle.service_id,
                created_by=subtitle.created_by,
                created_at=subtitle.created_at,
                segments=segments,
                provider=None,  # Skip provider to avoid lazy loading
                service=None,   # Skip service to avoid lazy loading
            )

    async def get_subtitle_segments(
        self, subtitle_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[SubtitleSegmentResponse]:
        """Get subtitle segments with pagination for streaming."""
        segments = await self.repo.get_segments(subtitle_id, limit=limit, offset=offset)
        return [
            SubtitleSegmentResponse(
                id=seg.id,
                subtitle_id=seg.subtitle_id,
                idx=seg.idx,
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                words=seg.words,
                created_at=seg.created_at,
            )
            for seg in segments
        ]

    async def search_subtitles(self, video_url: str, limit: int = 50, offset: int = 0) -> List[SubtitleListResponse]:
        """Search subtitles by video URL with pagination."""
        video_id = extract_video_id(video_url)
        if not video_id:
            raise InvalidVideoURLError()

        subtitles = await self.repo.get_subtitles_by_video_id(video_id, limit=limit, offset=offset)
        return [
            SubtitleListResponse(
                id=s.id,
                video_id=s.video_id,
                video_url=s.video_url,
                provider_id=s.provider_id,
                service_id=s.service_id,
                created_by=s.created_by,
                created_at=s.created_at,
                segment_count=len(s.segments) if s.segments else 0,
            )
            for s in subtitles
        ]

    async def get_user_settings(self, user_id: UUID):
        """Get user settings."""
        settings = await self.repo.get_user_settings(user_id)
        if not settings:
            from mugiko.modules.media.subtitle.service.dtos import UserSettingsResponse
            return UserSettingsResponse(user_id=user_id, schema_version=1, data={}, updated_at=__import__('datetime').datetime.utcnow())
        from mugiko.modules.media.subtitle.service.dtos import UserSettingsResponse
        # Manually construct response to avoid greenlet issues with lazy loading
        return UserSettingsResponse(
            user_id=settings.user_id,
            schema_version=settings.schema_version,
            data=settings.data,
            updated_at=settings.updated_at,
        )

    async def update_user_settings(self, user_id: UUID, data):
        """Update user settings."""
        from mugiko.modules.media.subtitle.service.dtos import UserSettingsResponse
        settings = await self.repo.upsert_user_settings(user_id, data.schema_version, data.data)
        # Manually construct response to avoid greenlet issues with lazy loading
        return UserSettingsResponse(
            user_id=settings.user_id,
            schema_version=settings.schema_version,
            data=settings.data,
            updated_at=settings.updated_at,
        )

    async def get_subtitle_user_state(self, user_id: UUID, subtitle_id: UUID):
        """Get subtitle user state."""
        state = await self.repo.get_user_state(user_id, subtitle_id)
        if not state:
            from mugiko.modules.media.subtitle.service.dtos import SubtitleUserStateResponse
            return SubtitleUserStateResponse(user_id=user_id, subtitle_id=subtitle_id, schema_version=1, data={}, updated_at=__import__('datetime').datetime.utcnow())
        from mugiko.modules.media.subtitle.service.dtos import SubtitleUserStateResponse
        # Manually construct response to avoid greenlet issues with lazy loading
        return SubtitleUserStateResponse(
            user_id=state.user_id,
            subtitle_id=state.subtitle_id,
            schema_version=state.schema_version,
            data=state.data,
            updated_at=state.updated_at,
        )

    async def update_subtitle_user_state(self, user_id: UUID, subtitle_id: UUID, data):
        """Update subtitle user state."""
        from mugiko.modules.media.subtitle.service.dtos import SubtitleUserStateResponse
        state = await self.repo.upsert_user_state(user_id, subtitle_id, data.schema_version, data.data)
        # Manually construct response to avoid greenlet issues with lazy loading
        return SubtitleUserStateResponse(
            user_id=state.user_id,
            subtitle_id=state.subtitle_id,
            schema_version=state.schema_version,
            data=state.data,
            updated_at=state.updated_at,
        )
