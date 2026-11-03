"""Pydantic models for stream messages."""
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime


class ConversationMessage(BaseModel):
    """Message from Sequin stream (new user message in conversation)."""
    conversation_id: UUID
    message_id: UUID = Field(validation_alias="id")
    user_id: Optional[str] = None
    role: str = "user"
    content: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True


class LLMJobMessage(BaseModel):
    """Job message from Sequin stream (new LLM job created)."""
    id: UUID
    prompt: str
    created_by: str
    model: Optional[str] = None
    conversation_id: Optional[UUID] = None
    status: str = "queued"
    response: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True


class LLMResponse(BaseModel):
    """Response to write back to DB and publish to output stream."""
    conversation_id: UUID
    message_id: UUID  # The assistant message ID
    response_content: str
    latency_ms: int
    status: str  # "completed" | "failed"
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class LLMJobResponse(BaseModel):
    """Response for LLM job completion."""
    job_id: UUID
    response: str
    latency_ms: int
    status: str  # "completed" | "failed"
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True