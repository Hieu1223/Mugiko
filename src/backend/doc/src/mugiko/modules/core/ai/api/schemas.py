from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class AIKeyCreate(BaseModel):
    service: str = Field(..., description="Service identifier (e.g., 'nim')")
    label: str = Field(..., min_length=1, max_length=100, description="Human-readable label")
    api_key: str = Field(..., min_length=1, description="The API key value")


class AIKeyResponse(BaseModel):
    id: UUID
    service: str
    label: str
    api_key_masked: str  # Last 4 chars only
    is_active: bool
    created_at: str
    last_used_at: Optional[str]
    last_test_at: Optional[str]
    last_test_ok: Optional[bool]


class AIKeyTestResponse(BaseModel):
    ok: bool
    error: Optional[str]
    latency_ms: int


class AIServiceSettingsResponse(BaseModel):
    service: str
    model: str
    dispatch_algorithm: str
    updated_at: str
    key_count: int


class AIServiceModelUpdate(BaseModel):
    model: str = Field(..., min_length=1, max_length=100)


class AIServiceListResponse(BaseModel):
    services: list[AIServiceSettingsResponse]