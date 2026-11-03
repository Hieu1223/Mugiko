import asyncio
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from mugiko.modules.core.ai.persistent.repository import AIRequestRepository, AIApiKeyRepository
from mugiko.modules.core.ai.provider.base import Message
from mugiko.modules.core.ai.provider.registry import provider_registry
from mugiko.modules.core.ai.service.gateway import AIGateway
from mugiko.common.persistent.session import async_session_maker


class AIWorker:
    """Worker that processes queued AI requests."""
    
    def __init__(
        self,
        worker_id: str,
        service: str = "nim",
        lease_seconds: int = 300,
        poll_interval: float = 5.0,
        max_attempts: int = 3,
    ):
        self.worker_id = worker_id
        self.service = service
        self.lease_seconds = lease_seconds
        self.poll_interval = poll_interval
        self.max_attempts = max_attempts
        self._running = False
    
    async def start(self) -> None:
        """Start the worker loop."""
        self._running = True
        while self._running:
            try:
                await self._process_once()
            except Exception as e:
                print(f"Worker {self.worker_id} error: {e}")
            await asyncio.sleep(self.poll_interval)
    
    def stop(self) -> None:
        self._running = False
    
    async def _process_once(self) -> None:
        async with async_session_maker() as session:
            request_repo = AIRequestRepository(session)
            key_repo = AIApiKeyRepository(session)
            
            # Claim next queued request
            request = await request_repo.claim_next_queued(
                self.service, self.worker_id, self.lease_seconds
            )
            
            if not request:
                return  # No work available
            
            # Get the provider
            provider = provider_registry.get(self.service)
            if not provider:
                await request_repo.fail(
                    request.id, f"No provider for service {self.service}", retry=False, max_attempts=self.max_attempts
                )
                await session.commit()
                return
            
            # Get API key
            if not request.api_key_id:
                await request_repo.fail(
                    request.id, "No available API key", retry=True, max_attempts=self.max_attempts
                )
                await session.commit()
                return
            
            key = await key_repo.get(request.api_key_id)
            if not key:
                await request_repo.fail(
                    request.id, "API key not found", retry=False, max_attempts=self.max_attempts
                )
                await session.commit()
                return
            
            # Convert prompt to messages
            messages = [Message(role=m["role"], content=m["content"]) for m in request.prompt]
            
            # Call provider
            try:
                start = time.perf_counter()
                result = await provider.complete(key.api_key, request.model, messages, request.params)
                latency_ms = int((time.perf_counter() - start) * 1000)
                
                await request_repo.complete(request.id, result.response, latency_ms)
                await key_repo.update_last_used(key.id)
                await session.commit()
                
                # Notify gateway
                # In a real implementation, this would use PostgreSQL NOTIFY
                # For now, we'll just print
                print(f"Request {request.id} completed successfully")
                
            except Exception as e:
                # Determine if retryable
                retryable = self._is_retryable(e)
                await request_repo.fail(request.id, str(e), retry=retryable, max_attempts=self.max_attempts)
                await session.commit()
                print(f"Request {request.id} failed: {e}")
    
    def _is_retryable(self, error: Exception) -> bool:
        """Determine if an error is retryable."""
        error_str = str(error).lower()
        # Rate limits, 5xx, timeouts
        return any(keyword in error_str for keyword in ["rate limit", "429", "500", "502", "503", "504", "timeout"])


class AIWorkerManager:
    """Manages multiple workers."""
    
    def __init__(self):
        self.workers: list[AIWorker] = []
        self.tasks: list[asyncio.Task] = []
    
    async def start(self, num_workers: int = 2, service: str = "nim") -> None:
        """Start the specified number of workers."""
        for i in range(num_workers):
            worker = AIWorker(worker_id=f"{service}-worker-{i}-{uuid.uuid4().hex[:8]}", service=service)
            self.workers.append(worker)
            task = asyncio.create_task(worker.start())
            self.tasks.append(task)
    
    async def stop(self) -> None:
        """Stop all workers."""
        for worker in self.workers:
            worker.stop()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)


# Recovery task
async def run_recovery_task(interval: int = 60) -> None:
    """Periodically recover stale running requests."""
    while True:
        try:
            async with async_session_maker() as session:
                request_repo = AIRequestRepository(session)
                recovered = await request_repo.recover_stale_running()
                if recovered > 0:
                    print(f"Recovered {recovered} stale requests")
                await session.commit()
        except Exception as e:
            print(f"Recovery task error: {e}")
        await asyncio.sleep(interval)