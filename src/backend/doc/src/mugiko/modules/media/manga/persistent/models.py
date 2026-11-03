"""Manga module models."""
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Enum as SQLEnum, Text, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from mugiko.common.persistent.session import Base
from mugiko.modules.core.user_management.persistent.models import UserAuth, GUID


class ProviderVisibility(str, enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class MangaProvider(Base):
    __tablename__ = "manga_providers"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(GUID, ForeignKey("user_auths.user_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    base_url = Column(String(500), nullable=False)
    visibility = Column(SQLEnum(ProviderVisibility, values_callable=lambda x: [e.value for e in x]), nullable=False, default=ProviderVisibility.PRIVATE)
    is_builtin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    owner = relationship("UserAuth", foreign_keys=[owner_id])
    subscriptions = relationship("MangaSubscription", back_populates="provider", cascade="all, delete-orphan")
    history = relationship("MangaHistory", back_populates="provider", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_manga_providers_owner_id", "owner_id"),
        Index("ix_manga_providers_owner_base_url", "owner_id", "base_url", unique=True),
        Index("ix_manga_providers_visibility", "visibility"),
    )


class MangaSubscription(Base):
    __tablename__ = "manga_subscriptions"

    user_id = Column(GUID, ForeignKey("user_auths.user_id", ondelete="CASCADE"), primary_key=True)
    provider_id = Column(PGUUID(as_uuid=True), ForeignKey("manga_providers.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("UserAuth", foreign_keys=[user_id])
    provider = relationship("MangaProvider", back_populates="subscriptions")


class MangaHistory(Base):
    __tablename__ = "manga_history"

    user_id = Column(GUID, ForeignKey("user_auths.user_id", ondelete="CASCADE"), primary_key=True)
    provider_id = Column(PGUUID(as_uuid=True), ForeignKey("manga_providers.id", ondelete="CASCADE"), primary_key=True)
    manga_id = Column(String(100), primary_key=True)
    chapter_id = Column(String(100), nullable=False)
    page_index = Column(Integer, default=0, nullable=False)
    title = Column(String(500), nullable=False)
    cover_url = Column(String(500), nullable=True)
    last_read_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("UserAuth", foreign_keys=[user_id])
    provider = relationship("MangaProvider", back_populates="history")

    __table_args__ = (
        Index("ix_manga_history_user_last_read", "user_id", "last_read_at"),
    )


class MangaUserSettings(Base):
    __tablename__ = "manga_user_settings"

    user_id = Column(GUID, ForeignKey("user_auths.user_id", ondelete="CASCADE"), primary_key=True)
    schema_version = Column(Integer, default=1, nullable=False)
    data = Column(JSONB().with_variant(SQLiteJSON, "sqlite"), nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("UserAuth", foreign_keys=[user_id])


# Built-in provider tables
class BuiltinManga(Base):
    __tablename__ = "builtin_manga"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(200), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    alternative_titles = Column(JSONB().with_variant(SQLiteJSON, "sqlite"), nullable=False, default=list)
    description = Column(Text, nullable=True)  # HTML
    source_url = Column(String(500), nullable=True)
    score = Column(Integer, default=0, nullable=False)
    views = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    cover_template_id = Column(PGUUID(as_uuid=True), ForeignKey("builtin_image_templates.id"), nullable=True)
    thumbnail_template_id = Column(PGUUID(as_uuid=True), ForeignKey("builtin_image_templates.id"), nullable=True)
    cover_vars = Column(JSONB().with_variant(SQLiteJSON, "sqlite"), nullable=True)

    tags = relationship("BuiltinMangaTag", back_populates="manga", cascade="all, delete-orphan")
    chapters = relationship("BuiltinChapter", back_populates="manga", cascade="all, delete-orphan")


class BuiltinTag(Base):
    __tablename__ = "builtin_tags"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)

    manga_tags = relationship("BuiltinMangaTag", back_populates="tag", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_builtin_tags_category_slug", "category", "slug", unique=True),
    )


class BuiltinMangaTag(Base):
    __tablename__ = "builtin_manga_tags"

    manga_id = Column(PGUUID(as_uuid=True), ForeignKey("builtin_manga.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(PGUUID(as_uuid=True), ForeignKey("builtin_tags.id", ondelete="CASCADE"), primary_key=True)

    manga = relationship("BuiltinManga", back_populates="tags")
    tag = relationship("BuiltinTag", back_populates="manga_tags")


class BuiltinChapter(Base):
    __tablename__ = "builtin_chapters"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manga_id = Column(PGUUID(as_uuid=True), ForeignKey("builtin_manga.id", ondelete="CASCADE"), nullable=False)
    number = Column(String(50), nullable=False)  # e.g., "20.3"
    sort_key = Column(Integer, nullable=False)  # for ordering
    title = Column(String(500), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=False)

    image_template_id = Column(PGUUID(as_uuid=True), ForeignKey("builtin_image_templates.id"), nullable=True)
    image_vars = Column(JSONB().with_variant(SQLiteJSON, "sqlite"), nullable=True)

    manga = relationship("BuiltinManga", back_populates="chapters")
    image_template = relationship("BuiltinImageTemplate", back_populates="chapters")
    pages = relationship("BuiltinPage", back_populates="chapter", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_builtin_chapters_manga_id", "manga_id"),
        Index("ix_builtin_chapters_sort_key", "manga_id", "sort_key"),
    )


class BuiltinPage(Base):
    __tablename__ = "builtin_pages"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id = Column(PGUUID(as_uuid=True), ForeignKey("builtin_chapters.id", ondelete="CASCADE"), nullable=False)
    idx = Column(Integer, nullable=False)
    name = Column(String(200), nullable=True)  # for {name} placeholder

    chapter = relationship("BuiltinChapter", back_populates="pages")

    __table_args__ = (
        Index("ix_builtin_pages_chapter_idx", "chapter_id", "idx", unique=True),
    )


class BuiltinImageTemplate(Base):
    __tablename__ = "builtin_image_templates"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    template = Column(String(500), nullable=False)  # URL template string

    cover_mangas = relationship("BuiltinManga", foreign_keys=[BuiltinManga.cover_template_id])
    thumbnail_mangas = relationship("BuiltinManga", foreign_keys=[BuiltinManga.thumbnail_template_id])
    chapters = relationship("BuiltinChapter", back_populates="image_template")