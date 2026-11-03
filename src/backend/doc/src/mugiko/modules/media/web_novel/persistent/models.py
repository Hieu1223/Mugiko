"""Web novel module models."""
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Enum as SQLEnum, Text, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid

from mugiko.common.persistent.session import Base


class SourceEnum(str, enum.Enum):
    SYOSETSU = "syosetsu"


class Novel(Base):
    __tablename__ = "novels"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(SQLEnum(SourceEnum, name='source_enum'), nullable=False)
    source_id = Column(String(100), nullable=False)
    url = Column(Text, nullable=False)
    title = Column(String(500), nullable=False)
    author = Column(String(200), nullable=True)
    synopsis = Column(Text, nullable=True)
    added_by = Column(PGUUID(as_uuid=True), ForeignKey('user_auths.user_id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    chapters = relationship("Chapter", back_populates="novel", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_novels_added_by", "added_by"),
        Index("ix_novels_source_source_id", "source", "source_id"),
    )


class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(PGUUID(as_uuid=True), ForeignKey('novels.id', ondelete='CASCADE'), nullable=False)
    idx = Column(Integer, nullable=False)
    title = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    novel = relationship("Novel", back_populates="chapters")
    paragraphs = relationship("Paragraph", back_populates="chapter", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_chapters_novel_id", "novel_id"),
    )


class Paragraph(Base):
    __tablename__ = "paragraphs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id = Column(PGUUID(as_uuid=True), ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False)
    idx = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    words = Column(JSONB, nullable=False, default=list)

    chapter = relationship("Chapter", back_populates="paragraphs")

    __table_args__ = (
        Index("ix_paragraphs_chapter_id", "chapter_id"),
    )