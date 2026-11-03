"""Manga module persistent repository."""
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, delete, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mugiko.modules.media.manga.persistent.models import (
    MangaProvider,
    MangaSubscription,
    MangaHistory,
    MangaUserSettings,
    ProviderVisibility,
    BuiltinManga,
    BuiltinTag,
    BuiltinChapter,
    BuiltinPage,
    BuiltinImageTemplate,
    BuiltinMangaTag,
)


class MangaRepository:
    """Repository for manga module data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # Provider methods
    async def create_provider(
        self,
        owner_id: UUID,
        name: str,
        base_url: str,
        visibility: ProviderVisibility,
        is_builtin: bool = False,
    ) -> MangaProvider:
        """Create a new manga provider."""
        provider = MangaProvider(
            owner_id=owner_id,
            name=name,
            base_url=base_url,
            visibility=visibility,
            is_builtin=is_builtin,
        )
        self.session.add(provider)
        await self.session.flush()
        await self.session.refresh(provider)
        return provider

    async def get_provider(self, provider_id: UUID) -> Optional[MangaProvider]:
        """Get provider by ID."""
        result = await self.session.execute(
            select(MangaProvider).where(MangaProvider.id == provider_id)
        )
        return result.scalar_one_or_none()

    async def get_provider_by_owner_and_url(self, owner_id: UUID, base_url: str) -> Optional[MangaProvider]:
        """Get provider by owner and base_url."""
        result = await self.session.execute(
            select(MangaProvider).where(
                and_(MangaProvider.owner_id == owner_id, MangaProvider.base_url == base_url)
            )
        )
        return result.scalar_one_or_none()

    async def get_user_providers(self, user_id: UUID) -> List[MangaProvider]:
        """Get providers owned by user."""
        result = await self.session.execute(
            select(MangaProvider).where(MangaProvider.owner_id == user_id).order_by(MangaProvider.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_public_providers(self, page: int = 1, page_size: int = 20) -> tuple[List[MangaProvider], int]:
        """Get public providers with pagination."""
        query = select(MangaProvider).where(
            and_(MangaProvider.visibility == ProviderVisibility.PUBLIC, MangaProvider.is_builtin == False)
        ).order_by(MangaProvider.created_at.desc())

        total_result = await self.session.execute(select(func.count()).select_from(query.subquery()))
        total = total_result.scalar_one()

        result = await self.session.execute(query.offset((page - 1) * page_size).limit(page_size))
        return list(result.scalars().all()), total

    async def get_subscribable_providers(self, user_id: UUID) -> List[MangaProvider]:
        """Get providers user can subscribe to (public + own)."""
        result = await self.session.execute(
            select(MangaProvider).where(
                or_(
                    MangaProvider.visibility == ProviderVisibility.PUBLIC,
                    MangaProvider.owner_id == user_id,
                )
            ).order_by(MangaProvider.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_provider(self, provider: MangaProvider, **kwargs) -> MangaProvider:
        """Update provider fields."""
        for key, value in kwargs.items():
            if value is not None:
                setattr(provider, key, value)
        await self.session.flush()
        await self.session.refresh(provider)
        return provider

    async def delete_provider(self, provider_id: UUID) -> bool:
        """Delete provider by ID."""
        result = await self.session.execute(
            delete(MangaProvider).where(MangaProvider.id == provider_id)
        )
        return result.rowcount > 0

    # Subscription methods
    async def subscribe(self, user_id: UUID, provider_id: UUID) -> MangaSubscription:
        """Create subscription."""
        subscription = MangaSubscription(user_id=user_id, provider_id=provider_id)
        self.session.add(subscription)
        await self.session.flush()
        await self.session.refresh(subscription)
        return subscription

    async def unsubscribe(self, user_id: UUID, provider_id: UUID) -> bool:
        """Remove subscription."""
        result = await self.session.execute(
            delete(MangaSubscription).where(
                and_(MangaSubscription.user_id == user_id, MangaSubscription.provider_id == provider_id)
            )
        )
        return result.rowcount > 0

    async def get_subscription(self, user_id: UUID, provider_id: UUID) -> Optional[MangaSubscription]:
        """Get subscription."""
        result = await self.session.execute(
            select(MangaSubscription).where(
                and_(MangaSubscription.user_id == user_id, MangaSubscription.provider_id == provider_id)
            )
        )
        return result.scalar_one_or_none()

    async def get_user_subscriptions(self, user_id: UUID) -> List[MangaSubscription]:
        """Get user subscriptions with provider details."""
        result = await self.session.execute(
            select(MangaSubscription)
            .options(selectinload(MangaSubscription.provider))
            .where(MangaSubscription.user_id == user_id)
            .order_by(MangaSubscription.created_at.desc())
        )
        return list(result.scalars().all())

    async def is_subscribed(self, user_id: UUID, provider_id: UUID) -> bool:
        """Check if user is subscribed to provider."""
        sub = await self.get_subscription(user_id, provider_id)
        return sub is not None

    # History methods
    async def upsert_history(self, user_id: UUID, data: dict) -> MangaHistory:
        """Upsert history entry."""
        # Try to get existing
        result = await self.session.execute(
            select(MangaHistory).where(
                and_(
                    MangaHistory.user_id == user_id,
                    MangaHistory.provider_id == data["provider_id"],
                    MangaHistory.manga_id == data["manga_id"],
                )
            )
        )
        history = result.scalar_one_or_none()

        if history:
            # Update existing
            history.chapter_id = data["chapter_id"]
            history.page_index = data["page_index"]
            history.title = data["title"]
            history.cover_url = data.get("cover_url")
            history.last_read_at = datetime.utcnow()
        else:
            # Create new
            history = MangaHistory(
                user_id=user_id,
                provider_id=data["provider_id"],
                manga_id=data["manga_id"],
                chapter_id=data["chapter_id"],
                page_index=data["page_index"],
                title=data["title"],
                cover_url=data.get("cover_url"),
            )
            self.session.add(history)

        await self.session.flush()
        await self.session.refresh(history)
        return history

    async def get_user_history(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[MangaHistory], int]:
        """Get user reading history with pagination."""
        query = (
            select(MangaHistory)
            .options(selectinload(MangaHistory.provider))
            .where(MangaHistory.user_id == user_id)
            .order_by(desc(MangaHistory.last_read_at))
        )

        total_result = await self.session.execute(select(func.count()).select_from(query.subquery()))
        total = total_result.scalar_one()

        result = await self.session.execute(query.offset((page - 1) * page_size).limit(page_size))
        return list(result.scalars().all()), total

    async def delete_history(self, user_id: UUID, provider_id: UUID, manga_id: str) -> bool:
        """Delete history entry."""
        result = await self.session.execute(
            delete(MangaHistory).where(
                and_(
                    MangaHistory.user_id == user_id,
                    MangaHistory.provider_id == provider_id,
                    MangaHistory.manga_id == manga_id,
                )
            )
        )
        return result.rowcount > 0

    # Settings methods
    async def get_user_settings(self, user_id: UUID) -> Optional[MangaUserSettings]:
        """Get user settings."""
        result = await self.session.execute(
            select(MangaUserSettings).where(MangaUserSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert_user_settings(
        self,
        user_id: UUID,
        schema_version: Optional[int] = None,
        data: Optional[dict] = None,
    ) -> MangaUserSettings:
        """Upsert user settings."""
        result = await self.session.execute(
            select(MangaUserSettings).where(MangaUserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()

        if settings:
            if schema_version is not None:
                settings.schema_version = schema_version
            if data is not None:
                settings.data = data
            settings.updated_at = datetime.utcnow()
        else:
            settings = MangaUserSettings(
                user_id=user_id,
                schema_version=schema_version or 1,
                data=data or {},
            )
            self.session.add(settings)

        await self.session.flush()
        await self.session.refresh(settings)
        return settings

    # Built-in provider methods
    async def get_builtin_provider(self) -> Optional[MangaProvider]:
        """Get the built-in provider."""
        result = await self.session.execute(
            select(MangaProvider).where(MangaProvider.is_builtin == True)
        )
        return result.scalar_one_or_none()

    async def create_builtin_provider(self, owner_id: UUID, base_url: str) -> MangaProvider:
        """Create the built-in provider."""
        return await self.create_provider(
            owner_id=owner_id,
            name="Built-in Provider",
            base_url=base_url,
            visibility=ProviderVisibility.PUBLIC,
            is_builtin=True,
        )

    # Built-in manga methods
    async def get_builtin_manga(
        self,
        manga_id: UUID,
    ) -> Optional[BuiltinManga]:
        """Get built-in manga by ID with tags and chapters."""
        result = await self.session.execute(
            select(BuiltinManga)
            .options(
                selectinload(BuiltinManga.tags).selectinload(BuiltinMangaTag.tag),
                selectinload(BuiltinManga.chapters),
            )
            .where(BuiltinManga.id == manga_id)
        )
        return result.scalar_one_or_none()

    async def search_builtin_manga(
        self,
        q: Optional[str] = None,
        tags: Optional[str] = None,  # tag filter expression
        page: int = 1,
        page_size: int = 20,
        sort: Optional[str] = None,
    ) -> tuple[List[BuiltinManga], int]:
        """Search built-in manga with filters."""
        query = select(BuiltinManga).options(
            selectinload(BuiltinManga.tags).selectinload(BuiltinMangaTag.tag),
            selectinload(BuiltinManga.chapters),
        )

        # Title search
        if q:
            query = query.where(
                or_(
                    BuiltinManga.title.ilike(f"%{q}%"),
                    BuiltinManga.alternative_titles.op("@>")(func.jsonb_build_array(q)),
                )
            )

        # Tag filtering - simplified for now
        # TODO: Parse tag expression and build proper SQL
        # This is a placeholder - actual implementation would parse the tag filter

        # Sorting
        if sort == "updated":
            query = query.order_by(desc(BuiltinManga.updated_at))
        elif sort == "title":
            query = query.order_by(BuiltinManga.title)
        elif sort == "views":
            query = query.order_by(desc(BuiltinManga.views))
        else:
            query = query.order_by(desc(BuiltinManga.updated_at))

        total_result = await self.session.execute(select(func.count()).select_from(query.subquery()))
        total = total_result.scalar_one()

        result = await self.session.execute(query.offset((page - 1) * page_size).limit(page_size))
        return list(result.scalars().all()), total

    async def get_builtin_chapters(self, manga_id: UUID) -> List[BuiltinChapter]:
        """Get chapters for a manga."""
        result = await self.session.execute(
            select(BuiltinChapter)
            .where(BuiltinChapter.manga_id == manga_id)
            .order_by(BuiltinChapter.sort_key)
        )
        return list(result.scalars().all())

    async def get_builtin_chapter(
        self,
        chapter_id: UUID,
    ) -> Optional[BuiltinChapter]:
        """Get chapter by ID with pages."""
        result = await self.session.execute(
            select(BuiltinChapter)
            .options(selectinload(BuiltinChapter.pages))
            .where(BuiltinChapter.id == chapter_id)
        )
        return result.scalar_one_or_none()

    async def get_builtin_pages(self, chapter_id: UUID) -> List[BuiltinPage]:
        """Get pages for a chapter."""
        result = await self.session.execute(
            select(BuiltinPage)
            .where(BuiltinPage.chapter_id == chapter_id)
            .order_by(BuiltinPage.idx)
        )
        return list(result.scalars().all())

    async def get_builtin_tags(self, category: Optional[str] = None, page: int = 1, page_size: int = 50) -> tuple[List[BuiltinTag], int]:
        """Get built-in tags."""
        query = select(BuiltinTag)
        if category:
            query = query.where(BuiltinTag.category == category)

        total_result = await self.session.execute(select(func.count()).select_from(query.subquery()))
        total = total_result.scalar_one()

        result = await self.session.execute(query.offset((page - 1) * page_size).limit(page_size))
        return list(result.scalars().all()), total

    # Image template methods
    async def get_image_template(self, template_id: UUID) -> Optional[BuiltinImageTemplate]:
        """Get image template by ID."""
        result = await self.session.execute(
            select(BuiltinImageTemplate).where(BuiltinImageTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    async def render_image_url(
        self,
        template: str,
        manga: BuiltinManga,
        chapter: Optional[BuiltinChapter] = None,
        page: Optional[BuiltinPage] = None,
        page_idx: int = 0,
        cover_vars: Optional[dict] = None,
        image_vars: Optional[dict] = None,
    ) -> str:
        """Render image URL from template."""
        import re

        vars_dict = {}
        if manga:
            vars_dict.update({
                "manga_id": str(manga.id),
                "manga_slug": manga.slug,
            })
        if chapter:
            vars_dict.update({
                "chapter_id": str(chapter.id),
                "chapter_number": chapter.number,
            })
        if page:
            vars_dict["name"] = page.name
        vars_dict["page"] = page_idx + 1  # 1-based
        vars_dict["index"] = page_idx    # 0-based

        if cover_vars:
            vars_dict.update(cover_vars)
        if image_vars:
            vars_dict.update(image_vars)

        def replace_placeholder(match):
            full = match.group(0)
            inner = match.group(1)
            if ':' in inner:
                key, fmt = inner.split(':', 1)
                val = vars_dict.get(key)
                if val is None:
                    raise ValueError(f"Unknown placeholder: {key}")
                # Handle zero-padding like {page:03}
                try:
                    width = int(fmt)
                    return str(val).zfill(width)
                except ValueError:
                    return str(val)
            else:
                val = vars_dict.get(inner)
                if val is None:
                    raise ValueError(f"Unknown placeholder: {inner}")
                return str(val)

        return re.sub(r'\{([^}]+)\}', replace_placeholder, template)