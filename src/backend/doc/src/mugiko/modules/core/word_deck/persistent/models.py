"""Database models for word deck module."""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.orm import relationship
import uuid

from mugiko.common.persistent.session import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type when available, otherwise uses CHAR(36).
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        return uuid.UUID(value)


class Deck(Base):
    """Deck table."""
    __tablename__ = "decks"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    owner_id = Column(GUID, ForeignKey("user_auths.user_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(__import__('datetime').timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(__import__('datetime').timezone.utc), onupdate=lambda: datetime.now(__import__('datetime').timezone.utc))

    # Relationship
    words = relationship("DeckWord", back_populates="deck", cascade="all, delete-orphan", order_by="DeckWord.created_at")

    # Constraints
    __table_args__ = (
        Index("ix_decks_owner_id", "owner_id"),
    )


class DeckWord(Base):
    """Deck word table."""
    __tablename__ = "deck_words"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    deck_id = Column(GUID, ForeignKey("decks.id", ondelete="CASCADE"), nullable=False)
    word = Column(String(255), nullable=False)
    meaning = Column(Text(), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(__import__('datetime').timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(__import__('datetime').timezone.utc), onupdate=lambda: datetime.now(__import__('datetime').timezone.utc))

    # Relationship
    deck = relationship("Deck", back_populates="words")

    # Constraints
    __table_args__ = (
        Index("ix_deck_words_deck_id", "deck_id"),
    )