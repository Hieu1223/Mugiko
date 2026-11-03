"""Subtitle provider models."""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, Text, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from mugiko.common.persistent.session import Base
from mugiko.modules.core.user_management.persistent.models import UserAuth, GUID


class ProviderKind(str, enum.Enum):
    REMOTE = "remote"
    YOUTUBE = "youtube"


class SubtitleProvider(Base):
    __tablename__ = "subtitle_providers"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    kind = Column(SQLEnum(ProviderKind, values_callable=lambda x: [e.value for e in x]), nullable=False)
    base_url = Column(String(500), nullable=True)  # null for YouTube
    is_active = Column(Boolean, default=True, nullable=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    services = relationship("SubtitleProviderService", back_populates="provider", cascade="all, delete-orphan")
    subtitles = relationship("Subtitle", back_populates="provider")


class SubtitleProviderService(Base):
    __tablename__ = "subtitle_provider_services"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    provider_id = Column(GUID, ForeignKey("subtitle_providers.id", ondelete="CASCADE"), nullable=False)
    service_key = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    options = Column(JSONB().with_variant(SQLiteJSON, "sqlite"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    provider = relationship("SubtitleProvider", back_populates="services")

    __table_args__ = (
        Index("ix_subtitle_provider_services_provider_service", "provider_id", "service_key", unique=True),
    )


class Subtitle(Base):
    __tablename__ = "subtitles"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    video_id = Column(String(50), nullable=False, index=True)  # normalized YouTube ID
    video_url = Column(String(500), nullable=False)
    provider_id = Column(GUID, ForeignKey("subtitle_providers.id"), nullable=False)
    service_id = Column(GUID, ForeignKey("subtitle_provider_services.id"), nullable=False)
    created_by = Column(GUID, ForeignKey("user_auths.user_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    provider = relationship("SubtitleProvider", back_populates="subtitles")
    service = relationship("SubtitleProviderService")
    creator = relationship("UserAuth", foreign_keys=[created_by])
    segments = relationship("SubtitleSegment", back_populates="subtitle", cascade="all, delete-orphan", order_by="SubtitleSegment.idx")
    access_records = relationship("SubtitleAccess", back_populates="subtitle", cascade="all, delete-orphan")
    user_states = relationship("SubtitleUserState", back_populates="subtitle", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_subtitles_video_id", "video_id"),
    )


class SubtitleSegment(Base):
    __tablename__ = "subtitle_segments"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    subtitle_id = Column(GUID, ForeignKey("subtitles.id", ondelete="CASCADE"), nullable=False)
    idx = Column(Integer, nullable=False)
    start_ms = Column(Integer, nullable=False)
    end_ms = Column(Integer, nullable=False)
    words = Column(JSONB().with_variant(SQLiteJSON, "sqlite"), nullable=True)  # list of {text, start_ms?, end_ms?, hiragana?}
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    subtitle = relationship("Subtitle", back_populates="segments")

    __table_args__ = (
        Index("ix_subtitle_segments_subtitle_idx", "subtitle_id", "idx", unique=True),
    )


class SubtitleAccess(Base):
    __tablename__ = "subtitle_access"

    user_id = Column(GUID, ForeignKey("user_auths.user_id", ondelete="CASCADE"), primary_key=True)
    subtitle_id = Column(GUID, ForeignKey("subtitles.id", ondelete="CASCADE"), primary_key=True)
    last_accessed_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    subtitle = relationship("Subtitle", back_populates="access_records")
    user = relationship("UserAuth", foreign_keys=[user_id])


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id = Column(GUID, ForeignKey("user_auths.user_id", ondelete="CASCADE"), primary_key=True)
    schema_version = Column(Integer, default=1, nullable=False)
    data = Column(JSONB().with_variant(SQLiteJSON, "sqlite"), nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("UserAuth", foreign_keys=[user_id])


class SubtitleUserState(Base):
    __tablename__ = "subtitle_user_state"

    user_id = Column(GUID, ForeignKey("user_auths.user_id", ondelete="CASCADE"), primary_key=True)
    subtitle_id = Column(GUID, ForeignKey("subtitles.id", ondelete="CASCADE"), primary_key=True)
    schema_version = Column(Integer, default=1, nullable=False)
    data = Column(JSONB().with_variant(SQLiteJSON, "sqlite"), nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    subtitle = relationship("Subtitle", back_populates="user_states")
    user = relationship("UserAuth", foreign_keys=[user_id])