from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from mugiko.modules.core.ai.persistent.repository import AIApiKeyRepository, AIServiceSettingsRepository
from mugiko.modules.core.ai.persistent.models import AIApiKey, AIServiceSettings
from mugiko.modules.core.ai.persistent.dtos import AIApiKeyDTO, AIServiceSettingsDTO


class AIKeyTestResult:
    def __init__(self, ok: bool, error: Optional[str], latency_ms: int):
        self.ok = ok
        self.error = error
        self.latency_ms = latency_ms


class AIKeyService:
    def __init__(self, repo: AIApiKeyRepository):
        self.repo = repo

    async def add_key(self, service: str, label: str, api_key: str) -> AIApiKeyDTO:
        key = await self.repo.create(service, label, api_key)
        return self._to_dto(key)

    async def list_keys(self, service: str, active_only: bool = True) -> list[AIApiKeyDTO]:
        keys = await self.repo.list_by_service(service, active_only)
        return [self._to_dto(k) for k in keys]

    async def delete_key(self, key_id: UUID) -> bool:
        return await self.repo.delete(key_id)

    async def test_key(self, key_id: UUID, provider) -> AIKeyTestResult:
        key = await self.repo.get(key_id)
        if not key:
            return AIKeyTestResult(ok=False, error="Key not found", latency_ms=0)
        
        result = await provider.test_key(key.api_key)
        await self.repo.update_test_result(key_id, result.ok)
        return AIKeyTestResult(ok=result.ok, error=result.error, latency_ms=result.latency_ms)

    def _to_dto(self, key: AIApiKey) -> AIApiKeyDTO:
        return AIApiKeyDTO(
            id=key.id,
            service=key.service,
            label=key.label,
            api_key=key.api_key,  # Note: in production, mask this in responses
            is_active=key.is_active,
            created_at=key.created_at,
            last_used_at=key.last_used_at,
            last_test_at=key.last_test_at,
            last_test_ok=key.last_test_ok,
        )


class AISettingsService:
    def __init__(self, repo: AIServiceSettingsRepository):
        self.repo = repo

    async def get_settings(self, service: str) -> Optional[AIServiceSettingsDTO]:
        settings = await self.repo.get(service)
        if not settings:
            return None
        return AIServiceSettingsDTO(
            service=settings.service,
            model=settings.model,
            dispatch_algorithm=settings.dispatch_algorithm,
            updated_at=settings.updated_at,
        )

    async def set_model(self, service: str, model: str) -> AIServiceSettingsDTO:
        settings = await self.repo.upsert(service, model)
        return AIServiceSettingsDTO(
            service=settings.service,
            model=settings.model,
            dispatch_algorithm=settings.dispatch_algorithm,
            updated_at=settings.updated_at,
        )

    async def list_all(self) -> list[AIServiceSettingsDTO]:
        settings_list = await self.repo.list_all()
        return [
            AIServiceSettingsDTO(
                service=s.service,
                model=s.model,
                dispatch_algorithm=s.dispatch_algorithm,
                updated_at=s.updated_at,
            )
            for s in settings_list
        ]