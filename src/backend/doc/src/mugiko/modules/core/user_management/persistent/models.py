"""Database models for user management."""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Enum as SQLEnum, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.orm import relationship
import uuid
import enum

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


class AuthType(str, enum.Enum):
    """Authentication type."""
    FIREBASE = "firebase"
    ADMIN = "admin"
    ANONYMOUS = "anonymous"


class Role(str, enum.Enum):
    """User role."""
    ANONYMOUS = "anonymous"
    USER = "user"
    ADMIN = "admin"


class UserAuth(Base):
    """User authentication table."""
    __tablename__ = "user_auths"
    
    user_id = Column(GUID, primary_key=True, default=uuid.uuid4)
    role = Column(SQLEnum(Role, values_callable=lambda x: [e.value for e in x]), nullable=False, default=Role.ANONYMOUS)
    joined_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(__import__('datetime').timezone.utc))
    auth_type = Column(SQLEnum(AuthType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    auth_id = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    
    # Relationship
    profile = relationship("UserProfile", back_populates="user_auth", uselist=False, cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("auth_type", "auth_id", name="uq_auth_type_auth_id"),
        Index("ix_user_auths_auth_type_auth_id", "auth_type", "auth_id"),
    )


class UserProfile(Base):
    """User profile table."""
    __tablename__ = "user_profiles"
    
    user_id = Column(GUID, ForeignKey("user_auths.user_id", ondelete="CASCADE"), primary_key=True)
    name = Column(String(100), nullable=False)
    bio = Column(String(500), nullable=True)
    email = Column(String(255), nullable=True)
    
    # Relationship
    user_auth = relationship("UserAuth", back_populates="profile")