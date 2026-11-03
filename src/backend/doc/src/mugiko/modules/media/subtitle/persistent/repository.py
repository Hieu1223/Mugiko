"""Subtitle repository for data access."""
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mugiko.modules.media.subtitle.persistent.models import (
    SubtitleProvider,
    SubtitleProviderService,
    Subtitle,
    SubtitleSegment,
    SubtitleAccess,
    UserSettings,
    SubtitleUserState,
    ProviderKind,
)


class SubtitleRepository:
    """Repository for subtitle module data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # Provider methods
    async def create_provider(
        self,
        name: str,
        kind: ProviderKind,
        base_url: Optional[str] = None,
    ) -> SubtitleProvider:
        provider = SubtitleProvider(name=name, kind=kind, base_url=base_url)
        self.session.add(provider)
        await self.session.flush()
        return provider

    async def get_provider(self, provider_id: UUID) -> Optional[SubtitleProvider]:
        result = await self.session.execute(
            select(SubtitleProvider)
            .options(selectinload(SubtitleProvider.services))
            .where(SubtitleProvider.id == provider_id)
        )
        return result.scalar_one_or_none()

    async def get_active_providers(self) -> List[SubtitleProvider]:
        result = await self.session.execute(
            select(SubtitleProvider)
            .options(selectinload(SubtitleProvider.services))
            .where(SubtitleProvider.is_active == True)
        )
        return list(result.scalars().all())

    async def update_provider_sync_time(self, provider_id: UUID) -> None:
        provider = await self.get_provider(provider_id)
        if provider:
            provider.last_synced_at = func.now()
            await self.session.flush()

    async def delete_provider(self, provider_id: UUID) -> bool:
        provider = await self.get_provider(provider_id)
        if provider:
            await self.session.delete(provider)
            await self.session.flush()
            return True
        return False

    # Provider service methods
    async def upsert_services(
        self, provider_id: UUID, services: List[dict]
    ) -> List[SubtitleProviderService]:
        # Deactivate all existing services for this provider
        await self.session.execute(
            SubtitleProviderService.__table__.update()
            .where(SubtitleProviderService.provider_id == provider_id)
            .values(is_active=False)
        )

        new_services = []
        for svc in services:
            service = SubtitleProviderService(
                provider_id=provider_id,
                service_key=svc["service_key"],
                name=svc["name"],
                options=svc.get("options"),
                is_active=True,
            )
            self.session.add(service)
            new_services.append(service)

        await self.session.flush()
        return new_services

    # Subtitle methods
    async def create_subtitle(
        self,
        video_id: str,
        video_url: str,
        provider_id: UUID,
        service_id: UUID,
        created_by: UUID,
    ) -> Subtitle:
        subtitle = Subtitle(
            video_id=video_id,
            video_url=video_url,
            provider_id=provider_id,
            service_id=service_id,
            created_by=created_by,
        )
        self.session.add(subtitle)
        await self.session.flush()
        return subtitle

    async def get_subtitle(self, subtitle_id: UUID) -> Optional[Subtitle]:
        result = await self.session.execute(
            select(Subtitle)
            .options(
                selectinload(Subtitle.segments),
                selectinload(Subtitle.provider),
                selectinload(Subtitle.service),
            )
            .where(Subtitle.id == subtitle_id)
        )
        return result.scalar_one_or_none()

    async def get_subtitles_by_video_id(self, video_id: str, limit: int = 50, offset: int = 0) -> List[Subtitle]:
        result = await self.session.execute(
            select(Subtitle)
            .options(
                selectinload(Subtitle.provider),
                selectinload(Subtitle.service),
                selectinload(Subtitle.segments),
            )
            .where(Subtitle.video_id == video_id)
            .order_by(Subtitle.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def add_segments(
        self, subtitle_id: UUID, segments: List[dict]
    ) -> List[SubtitleSegment]:
        subtitle_segments = []
        for idx, seg in enumerate(segments):
            segment = SubtitleSegment(
                subtitle_id=subtitle_id,
                idx=idx,
                start_ms=seg["start_ms"],
                end_ms=seg["end_ms"],
                words=seg.get("words"),
            )
            self.session.add(segment)
            subtitle_segments.append(segment)
        await self.session.flush()
        return subtitle_segments

    async def get_segments(
        self, subtitle_id: UUID, limit: int = 100, offset: int = 0
    ) -> List[SubtitleSegment]:
        result = await self.session.execute(
            select(SubtitleSegment)
            .where(SubtitleSegment.subtitle_id == subtitle_id)
            .order_by(SubtitleSegment.idx)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    # Subtitle access methods
    async def upsert_access(self, user_id: UUID, subtitle_id: UUID) -> SubtitleAccess:
        result = await self.session.execute(
            select(SubtitleAccess).where(
                SubtitleAccess.user_id == user_id,
                SubtitleAccess.subtitle_id == subtitle_id,
            )
        )
        access = result.scalar_one_or_none()
        if access:
            access.last_accessed_at = func.now()
        else:
            access = SubtitleAccess(user_id=user_id, subtitle_id=subtitle_id)
            self.session.add(access)
        await self.session.flush()
        return access

    # User settings methods
    async def get_user_settings(self, user_id: UUID) -> Optional[UserSettings]:
        result = await self.session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert_user_settings(
            self, user_id: UUID, schema_version: int, data: dict
        ) -> UserSettings:
            settings = await self.get_user_settings(user_id)
            if settings:
                settings.schema_version = schema_version
                settings.data = data
            else:
                settings = UserSettings(
                    user_id=user_id,
                    schema_version=schema_version,
                    data=data,
                )
                self.session.add(settings)
            await self.session.flush()
            await self.session.refresh(settings)
            return settings

    # Subtitle user state methods
    async def get_user_state(self, user_id: UUID, subtitle_id: UUID) -> Optional[SubtitleUserState]:
        result = await self.session.execute(
            select(SubtitleUserState).where(
                SubtitleUserState.user_id == user_id,
                SubtitleUserState.subtitle_id == subtitle_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_user_state(
        self, user_id: UUID, subtitle_id: UUID, schema_version: int, data: dict
    ) -> SubtitleUserState:
        state = await self.get_user_state(user_id, subtitle_id)
        if state:
            state.schema_version = schema_version
            state.data = data
        else:
            state = SubtitleUserState(
                user_id=user_id,
                subtitle_id=subtitle_id,
                schema_version=schema_version,
                data=data,
            )
            self.session.add(state)
        await self.session.flush()
        await self.session.refresh(state)
        return state
