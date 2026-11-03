from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mugiko.modules.core.ai.persistent.models import AIApiKey, AIRequest, AIServiceSettings


class AIApiKeyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, service: str, label: str, api_key: str) -> AIApiKey:
        key = AIApiKey(service=service, label=label, api_key=api_key)
        self.session.add(key)
        await self.session.flush()
        return key

    async def get(self, key_id: UUID) -> Optional[AIApiKey]:
        result = await self.session.execute(select(AIApiKey).where(AIApiKey.id == key_id))
        return result.scalar_one_or_none()

    async def list_by_service(self, service: str, active_only: bool = True) -> list[AIApiKey]:
        query = select(AIApiKey).where(AIApiKey.service == service)
        if active_only:
            query = query.where(AIApiKey.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def delete(self, key_id: UUID) -> bool:
        key = await self.get(key_id)
        if key:
            await self.session.delete(key)
            return True
        return False

    async def update_last_used(self, key_id: UUID) -> None:
        await self.session.execute(
            AIApiKey.__table__.update()
            .where(AIApiKey.id == key_id)
            .values(last_used_at=datetime.now(timezone.utc))
        )

    async def update_test_result(self, key_id: UUID, ok: bool) -> None:
        await self.session.execute(
            AIApiKey.__table__.update()
            .where(AIApiKey.id == key_id)
            .values(last_test_at=datetime.now(timezone.utc), last_test_ok=ok)
        )


class AIServiceSettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, service: str) -> Optional[AIServiceSettings]:
        result = await self.session.execute(select(AIServiceSettings).where(AIServiceSettings.service == service))
        return result.scalar_one_or_none()

    async def upsert(self, service: str, model: str, dispatch_algorithm: str = "round_robin") -> AIServiceSettings:
        settings = await self.get(service)
        if settings:
            settings.model = model
            settings.dispatch_algorithm = dispatch_algorithm
        else:
            settings = AIServiceSettings(service=service, model=model, dispatch_algorithm=dispatch_algorithm)
            self.session.add(settings)
        await self.session.flush()
        await self.session.refresh(settings)
        return settings

    async def list_all(self) -> list[AIServiceSettings]:
        result = await self.session.execute(select(AIServiceSettings))
        return list(result.scalars().all())


class AIRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        service: str,
        model: str,
        caller: str,
        prompt: list[dict],
        user_id: Optional[UUID] = None,
        params: Optional[dict] = None,
    ) -> AIRequest:
        request = AIRequest(
            service=service,
            model=model,
            caller=caller,
            user_id=user_id,
            prompt=prompt,
            params=params,
        )
        self.session.add(request)
        await self.session.flush()
        return request

    async def get(self, request_id: UUID) -> Optional[AIRequest]:
        result = await self.session.execute(select(AIRequest).where(AIRequest.id == request_id))
        return result.scalar_one_or_none()

    async def get_with_key(self, request_id: UUID) -> Optional[AIRequest]:
        result = await self.session.execute(
            select(AIRequest).options(selectinload(AIRequest.api_key)).where(AIRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def claim_next_queued(self, service: str, worker_id: str, lease_seconds: int = 300) -> Optional[AIRequest]:
        """Claim the next queued request for the service using FOR UPDATE SKIP LOCKED."""
        from sqlalchemy import text
        
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            text("""
                UPDATE ai_requests
                SET status = 'running',
                    locked_by = :worker_id,
                    lease_expires_at = :lease_expires,
                    attempts = attempts + 1,
                    api_key_id = (
                        SELECT id FROM ai_api_keys
                        WHERE service = :service
                          AND is_active = true
                          AND id NOT IN (
                              SELECT api_key_id FROM ai_requests
                              WHERE status = 'running' AND api_key_id IS NOT NULL
                          )
                        ORDER BY last_used_at ASC NULLS FIRST
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    ),
                    last_used_at = CASE WHEN api_key_id IS NOT NULL THEN now() END
                WHERE id = (
                    SELECT id FROM ai_requests
                    WHERE service = :service
                      AND status = 'queued'
                      AND (next_attempt_at IS NULL OR next_attempt_at <= now())
                    ORDER BY created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id
            """),
            {"service": service, "worker_id": worker_id, "lease_expires": now.replace(second=now.second + lease_seconds)},
        )
        row = result.first()
        if row:
            request = await self.get(row[0])
            return request
        return None

    async def complete(self, request_id: UUID, response: dict, latency_ms: int) -> bool:
        result = await self.session.execute(
            AIRequest.__table__.update()
            .where(AIRequest.id == request_id)
            .values(
                status="succeeded",
                response=response,
                latency_ms=latency_ms,
                completed_at=datetime.now(timezone.utc),
                lease_expires_at=None,
                locked_by=None,
            )
        )
        return result.rowcount > 0

    async def fail(self, request_id: UUID, error: str, retry: bool, max_attempts: int = 3) -> bool:
        request = await self.get(request_id)
        if not request:
            return False
        
        if retry and request.attempts < max_attempts:
            # Exponential backoff: 2^attempts * 1000ms
            backoff_ms = (2 ** request.attempts) * 1000
            from sqlalchemy import text
            await self.session.execute(
                text("""
                    UPDATE ai_requests
                    SET status = 'queued',
                        error = :error,
                        next_attempt_at = now() + (:backoff_ms || ' milliseconds')::interval,
                        lease_expires_at = NULL,
                        locked_by = NULL
                    WHERE id = :request_id
                """),
                {"request_id": request_id, "error": error, "backoff_ms": backoff_ms},
            )
        else:
            await self.session.execute(
                AIRequest.__table__.update()
                .where(AIRequest.id == request_id)
                .values(
                    status="failed",
                    error=error,
                    completed_at=datetime.now(timezone.utc),
                    lease_expires_at=None,
                    locked_by=None,
                )
            )
        return True

    async def cancel(self, request_id: UUID) -> bool:
        result = await self.session.execute(
            AIRequest.__table__.update()
            .where(AIRequest.id == request_id)
            .where(AIRequest.status.in_(["queued", "running"]))
            .values(
                status="cancelled",
                completed_at=datetime.now(timezone.utc),
                lease_expires_at=None,
                locked_by=None,
            )
        )
        return result.rowcount > 0

    async def recover_stale_running(self, lease_seconds: int = 300, max_attempts: int = 3) -> int:
        """Recover requests stuck in 'running' with expired lease."""
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            AIRequest.__table__.update()
            .where(
                AIRequest.status == "running",
                AIRequest.lease_expires_at < now,
                AIRequest.attempts < max_attempts,
            )
            .values(
                status="queued",
                lease_expires_at=None,
                locked_by=None,
                next_attempt_at=now,
            )
        )
        return result.rowcount

    async def count_queued(self, service: str) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(AIRequest).where(
                AIRequest.service == service, AIRequest.status == "queued"
            )
        )
        return result.scalar_one()