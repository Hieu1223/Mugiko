from typing import Protocol, Optional
from dataclasses import dataclass


@dataclass
class Message:
    role: str
    content: str


@dataclass
class AIResultDTO:
    response: dict
    latency_ms: int


@dataclass
class KeyTestDTO:
    ok: bool
    error: Optional[str]
    latency_ms: int


class AIServiceProvider(Protocol):
    service_key: str

    async def complete(self, api_key: str, model: str, messages: list[Message], params: Optional[dict]) -> AIResultDTO: ...

    async def test_key(self, api_key: str) -> KeyTestDTO: ...