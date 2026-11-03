import os
import time
import httpx
from typing import Optional

from mugiko.modules.core.ai.provider.base import AIServiceProvider, AIResultDTO, KeyTestDTO, Message


class NimProvider:
    """NVIDIA NIM provider - OpenAI-compatible chat completions."""
    
    service_key = "nim"
    
    def __init__(self):
        self.base_url = os.getenv("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
        self.timeout = float(os.getenv("NIM_TIMEOUT", "60.0"))
    
    async def complete(self, api_key: str, model: str, messages: list[Message], params: Optional[dict] = None) -> AIResultDTO:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if params:
            payload.update(params)
        
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        
        latency_ms = int((time.perf_counter() - start) * 1000)
        
        return AIResultDTO(
            response=data,
            latency_ms=latency_ms,
        )
    
    async def test_key(self, api_key: str) -> KeyTestDTO:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": "meta/llama-3.1-8b-instruct",
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 1,
        }
        
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                latency_ms = int((time.perf_counter() - start) * 1000)
                return KeyTestDTO(ok=True, error=None, latency_ms=latency_ms)
        except httpx.HTTPStatusError as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return KeyTestDTO(ok=False, error=f"HTTP {e.response.status_code}: {e.response.text}", latency_ms=latency_ms)
        except Exception as e:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return KeyTestDTO(ok=False, error=str(e), latency_ms=latency_ms)