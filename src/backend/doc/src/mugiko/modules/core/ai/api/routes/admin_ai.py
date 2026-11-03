from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from mugiko.common.persistent.session import get_session
from mugiko.modules.core.user_management.persistent.models import Role
from mugiko.modules.core.user_management.api.dependencies import require_roles, require_admin
from mugiko.modules.core.ai.service.settings_service import AIKeyService, AISettingsService
from mugiko.modules.core.ai.persistent.repository import AIApiKeyRepository, AIServiceSettingsRepository
from mugiko.modules.core.ai.provider.registry import provider_registry
from mugiko.modules.core.ai.api.schemas import (
    AIKeyCreate,
    AIKeyResponse,
    AIKeyTestResponse,
    AIServiceSettingsResponse,
    AIServiceModelUpdate,
    AIServiceListResponse,
)


router = APIRouter(prefix="/admin/ai", tags=["admin-ai"])


def get_key_service(session: AsyncSession = Depends(get_session)) -> AIKeyService:
    return AIKeyService(AIApiKeyRepository(session))


def get_settings_service(session: AsyncSession = Depends(get_session)) -> AISettingsService:
    return AISettingsService(AIServiceSettingsRepository(session))


@router.get("/services", response_model=AIServiceListResponse)
async def list_services(
    settings_service: AISettingsService = Depends(get_settings_service),
    key_service: AIKeyService = Depends(get_key_service),
    _: None = Depends(require_admin),
):
    """List all configured services with model, dispatch algorithm, and key counts."""
    settings_list = await settings_service.list_all()
    result = []
    for s in settings_list:
        keys = await key_service.list_keys(s.service, active_only=True)
        result.append(
            AIServiceSettingsResponse(
                service=s.service,
                model=s.model,
                dispatch_algorithm=s.dispatch_algorithm,
                updated_at=s.updated_at.isoformat(),
                key_count=len(keys),
            )
        )
    return AIServiceListResponse(services=result)


@router.get("/keys", response_model=list[AIKeyResponse])
async def list_keys(
    service: str = Query(..., description="Service identifier"),
    active_only: bool = True,
    key_service: AIKeyService = Depends(get_key_service),
    _: None = Depends(require_admin),
):
    """List keys for a service (key value masked, last 4 characters only)."""
    keys = await key_service.list_keys(service, active_only)
    return [
        AIKeyResponse(
            id=k.id,
            service=k.service,
            label=k.label,
            api_key_masked="****" + (k.api_key[-4:] if len(k.api_key) >= 4 else "****"),
            is_active=k.is_active,
            created_at=k.created_at.isoformat(),
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
            last_test_at=k.last_test_at.isoformat() if k.last_test_at else None,
            last_test_ok=k.last_test_ok,
        )
        for k in keys
    ]


@router.post("/keys", response_model=AIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    payload: AIKeyCreate,
    key_service: AIKeyService = Depends(get_key_service),
    _: None = Depends(require_admin),
):
    """Add a new API key for a service."""
    key = await key_service.add_key(payload.service, payload.label, payload.api_key)
    return AIKeyResponse(
        id=key.id,
        service=key.service,
        label=key.label,
        api_key_masked="****" + (key.api_key[-4:] if len(key.api_key) >= 4 else "****"),
        is_active=key.is_active,
        created_at=key.created_at.isoformat(),
        last_used_at=key.last_used_at.isoformat() if key.last_used_at else None,
        last_test_at=key.last_test_at.isoformat() if key.last_test_at else None,
        last_test_ok=key.last_test_ok,
    )


@router.delete("/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_key(
    key_id: UUID,
    key_service: AIKeyService = Depends(get_key_service),
    _: None = Depends(require_admin),
):
    """Delete an API key."""
    deleted = await key_service.delete_key(key_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Key not found")


@router.post("/keys/{key_id}/test", response_model=AIKeyTestResponse)
async def test_key(
    key_id: UUID,
    key_service: AIKeyService = Depends(get_key_service),
    _: None = Depends(require_admin),
):
    """Test an API key."""
    provider = provider_registry.get("nim")  # TODO: get from key's service
    if not provider:
        raise HTTPException(status_code=400, detail="No provider for service")
    
    result = await key_service.test_key(key_id, provider)
    return AIKeyTestResponse(ok=result.ok, error=result.error, latency_ms=result.latency_ms)


@router.put("/services/{service}/model", response_model=AIServiceSettingsResponse)
async def set_service_model(
    service: str,
    payload: AIServiceModelUpdate,
    settings_service: AISettingsService = Depends(get_settings_service),
    _: None = Depends(require_admin),
):
    """Set the model for a service."""
    # Verify provider exists
    if not provider_registry.get(service):
        raise HTTPException(status_code=400, detail=f"Unknown service: {service}")
    
    settings = await settings_service.set_model(service, payload.model)
    return AIServiceSettingsResponse(
        service=settings.service,
        model=settings.model,
        dispatch_algorithm=settings.dispatch_algorithm,
        updated_at=settings.updated_at.isoformat(),
        key_count=0,  # Would need to fetch separately
    )