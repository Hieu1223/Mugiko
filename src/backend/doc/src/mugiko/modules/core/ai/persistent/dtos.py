from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class AIApiKeyDTO:
    id: UUID
    service: str
    label: str
    api_key: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]
    last_test_at: Optional[datetime]
    last_test_ok: Optional[bool]


@dataclass
class AIServiceSettingsDTO:
    service: str
    model: str
    dispatch_algorithm: str
    updated_at: datetime


@dataclass
class AIRequestDTO:
    id: UUID
    service: str
    model: str
    caller: str
    user_id: Optional[UUID]
    prompt: list[dict]
    params: Optional[dict]
    status: str
    attempts: int
    next_attempt_at: Optional[datetime]
    api_key_id: Optional[UUID]
    locked_by: Optional[str]
    lease_expires_at: Optional[datetime]
    response: Optional[dict]
    error: Optional[str]
    latency_ms: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime]


@dataclass
class AIResultDTO:
    request_id: UUID
    response: dict
    latency_ms: int


@dataclass
class KeyTestDTO:
    ok: bool
    error: Optional[str]
    latency_ms: int