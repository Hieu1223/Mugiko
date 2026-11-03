from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mugiko.common.persistent.session import Base


class AIApiKey(Base):
    __tablename__ = "ai_api_keys"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    service: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_test_ok: Mapped[Optional[bool]] = mapped_column(nullable=True)

    requests: Mapped[list["AIRequest"]] = relationship(back_populates="api_key")


class AIServiceSettings(Base):
    __tablename__ = "ai_service_settings"

    service: Mapped[str] = mapped_column(String(50), primary_key=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    dispatch_algorithm: Mapped[str] = mapped_column(String(50), default="round_robin", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AIRequest(Base):
    __tablename__ = "ai_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    service: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    caller: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("user_auths.user_id", ondelete="SET NULL"), nullable=True)

    prompt: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(
        Enum("queued", "running", "succeeded", "failed", "cancelled", name="ai_request_status"),
        default="queued",
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    api_key_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("ai_api_keys.id", ondelete="SET NULL"), nullable=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    api_key: Mapped[Optional["AIApiKey"]] = relationship(back_populates="requests")

    __table_args__ = (
        Index("ix_ai_requests_service_status_next_attempt", "service", "status", "next_attempt_at"),
    )