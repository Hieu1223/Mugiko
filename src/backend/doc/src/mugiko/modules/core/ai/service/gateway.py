import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from mugiko.modules.core.ai.persistent.repository import AIRequestRepository, AIServiceSettingsRepository
from mugiko.modules.core.ai.persistent.models import AIRequest
from mugiko.modules.core.ai.provider.base import Message, AIResultDTO
from mugiko.modules.core.ai.provider.registry import provider_registry
from mugiko.modules.core.ai.persistent.dtos import AIRequestDTO


class AIGateway:
    """Gateway for other modules to submit AI requests."""
    
    def __init__(
        self,
        request_repo: AIRequestRepository,
        settings_repo: AIServiceSettingsRepository,
        queue_limit: int = 1000,
        poll_interval: float = 1.0,
    ):
        self.request_repo = request_repo
        self.settings_repo = settings_repo
        self.queue_limit = queue_limit
        self.poll_interval = poll_interval
        self._completion_events: dict[UUID, asyncio.Event] = {}
    
    async def submit(
        self,
        *,
        messages: list[Message],
        caller: str,
        user_id: Optional[UUID] = None,
        service: str = "nim",
        params: Optional[dict] = None,
    ) -> UUID:
        """Submit a request to the queue, return request ID."""
        # Check queue limit
        queued_count = await self.request_repo.count_queued(service)
        if queued_count >= self.queue_limit:
            raise AIQueueFullError(f"Queue limit ({self.queue_limit}) reached for service {service}")
        
        # Get current model for service
        settings = await self.settings_repo.get(service)
        if not settings:
            raise AIServiceNotConfiguredError(f"Service {service} not configured")
        
        # Create request
        request = await self.request_repo.create(
            service=service,
            model=settings.model,
            caller=caller,
            prompt=[{"role": m.role, "content": m.content} for m in messages],
            user_id=user_id,
            params=params,
        )
        
        # Notify workers (PostgreSQL NOTIFY would go here)
        # For now, workers poll
        
        return request.id
    
    async def get_result(self, request_id: UUID) -> AIRequestDTO:
        """Get the current state of a request."""
        request = await self.request_repo.get_with_key(request_id)
        if not request:
            raise AIRequestNotFoundError(f"Request {request_id} not found")
        return self._to_dto(request)
    
    async def complete(
        self,
        *,
        messages: list[Message],
        caller: str,
        user_id: Optional[UUID] = None,
        service: str = "nim",
        params: Optional[dict] = None,
        timeout: float = 60.0,
    ) -> AIResultDTO:
        """Submit and wait for completion."""
        request_id = await self.submit(
            messages=messages,
            caller=caller,
            user_id=user_id,
            service=service,
            params=params,
        )
        
        # Wait for completion
        start = asyncio.get_event_loop().time()
        event = asyncio.Event()
        self._completion_events[request_id] = event
        
        try:
            while True:
                request = await self.request_repo.get(request_id)
                if not request:
                    raise AIRequestNotFoundError(f"Request {request_id} not found")
                
                if request.status in ("succeeded", "failed", "cancelled"):
                    if request.status == "succeeded":
                        return AIResultDTO(
                            request_id=request.id,
                            response=request.response or {},
                            latency_ms=request.latency_ms or 0,
                        )
                    elif request.status == "cancelled":
                        raise AIRequestCancelledError(f"Request {request_id} was cancelled")
                    else:
                        raise AIRequestFailedError(f"Request {request_id} failed: {request.error}")
                
                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start
                if elapsed >= timeout:
                    # Try to cancel
                    await self.request_repo.cancel(request_id)
                    raise AIRequestTimeoutError(f"Request {request_id} timed out after {timeout}s")
                
                # Wait for notification or poll
                try:
                    await asyncio.wait_for(event.wait(), timeout=self.poll_interval)
                except asyncio.TimeoutError:
                    pass  # Continue polling
        finally:
            self._completion_events.pop(request_id, None)
    
    def notify_completion(self, request_id: UUID) -> None:
        """Called when a request completes (by worker)."""
        event = self._completion_events.get(request_id)
        if event:
            event.set()
    
    def _to_dto(self, request: AIRequest) -> AIRequestDTO:
        return AIRequestDTO(
            id=request.id,
            service=request.service,
            model=request.model,
            caller=request.caller,
            user_id=request.user_id,
            prompt=request.prompt,
            params=request.params,
            status=request.status,
            attempts=request.attempts,
            next_attempt_at=request.next_attempt_at,
            api_key_id=request.api_key_id,
            locked_by=request.locked_by,
            lease_expires_at=request.lease_expires_at,
            response=request.response,
            error=request.error,
            latency_ms=request.latency_ms,
            created_at=request.created_at,
            completed_at=request.completed_at,
        )


class AIQueueFullError(Exception):
    pass


class AIServiceNotConfiguredError(Exception):
    pass


class AIRequestNotFoundError(Exception):
    pass


class AIRequestCancelledError(Exception):
    pass


class AIRequestFailedError(Exception):
    pass


class AIRequestTimeoutError(Exception):
    pass