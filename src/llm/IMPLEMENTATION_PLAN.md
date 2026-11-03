# LLM Conversation Server Implementation Plan

## Overview
Create a new `llm_server` at `/c/Projects/llm_server` that handles LLM conversation processing via Redis streams from Sequin CDC.

## Architecture Flow
```
User → Main Server (MugikoGO) → DB (conversations/messages)
                                              ↓
                                      Sequin CDC (PostgreSQL logical replication)
                                              ↓
                                      Redis Stream (conversation_changes)
                                              ↓
                              LLM Server (new) processes messages
                                              ↓
                                      DB (write LLM response)
                                              ↓
                                      Sequin CDC → Redis Stream
                                              ↓
                              Main Server reads → SSE to User
```

## Files to Create

### 1. `/c/Projects/llm_server/` - New Project Root
```
llm_server/
├── Dockerfile
├── requirements.txt
├── .env.example
├── README.md
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── config.py            # Environment config
│   ├── listener.py          # Redis stream consumer (XREADGROUP)
│   ├── processor.py         # LLM processing logic
│   ├── repository.py        # DB operations (conversations, messages)
│   ├── nim_client.py        # NVIDIA NIM client (from MugikoWorkServer)
│   ├── models.py            # Pydantic models for stream messages
│   └── common/
│       ├── __init__.py
│       ├── db.py            # PostgreSQL connection
│       └── redis.py         # Redis connection helpers
└── alembic/                 # Database migrations (optional, can reuse Mugiko schema)
```

### 2. Database Schema Changes (in Mugiko/MugikoGO)
Need conversation and message tables that Sequin will watch.

### 3. Docker Compose Updates
- Add `llm_server` service to `doc/docker-compose.yml`
- Update network/configuration

### 4. Sequin Configuration
- Configure `playground.yml` to watch conversation/message tables
- Map to Redis streams

---

## Detailed Implementation Steps

### Phase 1: Database Schema (Mugiko/MugikoGO)
Add to `doc/schema.sql`:
```sql
-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(conversation_id, created_at);
```

### Phase 2: LLM Server Implementation

#### `requirements.txt`
```
redis>=5.0
psycopg2-binary>=2.9
python-dotenv>=1.0
requests>=2.32
pydantic>=2.0
pydantic-settings>=2.0
```

#### `config.py`
```python
"""Environment-driven configuration for LLM Server."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.local", override=True)

DEFAULT_KEYS_FILE = "nim.txt"

def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default

def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default

@dataclass(frozen=True)
class LLMServerConfig:
    # Database
    database_url: str
    
    # Redis
    redis_url: str
    consumer_group: str = "llm-workers"
    consumer_name: str = "worker-1"
    input_stream: str = "conversation_messages"  # From Sequin
    output_stream: str = "llm_responses"         # To Sequin/main server
    read_block_ms: int = 5000
    claim_idle_ms: int = 300000
    stream_maxlen: int = 10000
    
    # NVIDIA NIM
    api_keys_file: str
    base_url: str
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: float
    
    # Processing
    poll_interval_ms: int = 2000
    max_concurrent_jobs: int = 10

    @classmethod
    def from_env(cls) -> "LLMServerConfig":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL is required")
        
        return cls(
            database_url=database_url,
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            consumer_group=os.getenv("LLM_CONSUMER_GROUP", "llm-workers"),
            consumer_name=os.getenv("LLM_CONSUMER_NAME", "worker-1"),
            input_stream=os.getenv("LLM_INPUT_STREAM", "conversation_messages"),
            output_stream=os.getenv("LLM_OUTPUT_STREAM", "llm_responses"),
            read_block_ms=_env_int("LLM_READ_BLOCK_MS", 5000),
            claim_idle_ms=_env_int("LLM_CLAIM_IDLE_MS", 300000),
            stream_maxlen=_env_int("LLM_STREAM_MAXLEN", 10000),
            api_keys_file=os.getenv("NVIDIA_API_KEYS_FILE", DEFAULT_KEYS_FILE),
            base_url=os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/"),
            model=os.getenv("NVIDIA_NIM_MODEL", "deepseek-ai/deepseek-v4.1-flash"),
            temperature=_env_float("NVIDIA_NIM_TEMPERATURE", 0.2),
            max_tokens=_env_int("NVIDIA_NIM_MAX_TOKENS", 4096),
            timeout_seconds=_env_float("NVIDIA_NIM_TIMEOUT_SECONDS", 120.0),
            poll_interval_ms=_env_int("LLM_POLL_INTERVAL_MS", 2000),
            max_concurrent_jobs=_env_int("LLM_MAX_CONCURRENT_JOBS", 10),
        )

    def load_api_keys(self) -> list[str]:
        try:
            with open(self.api_keys_file, "r", encoding="utf-8") as f:
                keys = [line.strip() for line in f if line.strip()]
        except OSError as exc:
            raise RuntimeError(f"Cannot read NVIDIA key file {self.api_keys_file!r}: {exc}") from exc
        if not keys:
            raise RuntimeError(f"NVIDIA key file {self.api_keys_file!r} contains no keys")
        return keys
```

#### `models.py`
```python
"""Pydantic models for stream messages."""
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime

class ConversationMessage(BaseModel):
    """Message from Sequin stream (new user message in conversation)."""
    conversation_id: UUID
    message_id: UUID
    user_id: str
    role: str = "user"
    content: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime

class LLMResponse(BaseModel):
    """Response to write back to DB and publish to output stream."""
    conversation_id: UUID
    message_id: UUID  # The assistant message ID
    response_content: str
    latency_ms: int
    status: str  # "completed" | "failed"
    error: Optional[str] = None
```

#### `nim_client.py` (Adapted from MugikoWorkServer)
```python
"""NVIDIA NIM OpenAI-compatible chat completions client."""
import logging
import time
from typing import Any, List

import requests

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 1.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

class NIMError(RuntimeError):
    """A NIM request failed or returned an unusable response."""

def _extract_content(data: Any) -> str:
    try:
        message = data["choices"][0]["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise NIMError(f"Unexpected NIM response shape: {str(data)[:500]}") from exc

    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        content = "".join(parts)

    if not isinstance(content, str) or not content.strip():
        raise NIMError("NIM returned an empty response")
    return content

class NIMClient:
    def __init__(
        self,
        api_keys: List[str],
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float,
    ) -> None:
        if not api_keys:
            raise ValueError("api_keys must not be empty")
        self._api_keys = list(api_keys)
        self._next_key = 0
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds
        self._session = requests.Session()

    def _take_key(self) -> str:
        key = self._api_keys[self._next_key]
        self._next_key = (self._next_key + 1) % len(self._api_keys)
        return key

    def chat(self, messages: List[dict]) -> str:
        key = self._take_key()
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": False,
        }

        last_error: NIMError | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = self._session.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                    timeout=self._timeout,
                )
            except requests.RequestException as exc:
                last_error = NIMError(f"NIM request failed: {exc}")
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_RETRY_DELAY_SECONDS)
                    continue
                raise last_error from exc

            if response.status_code in _RETRYABLE_STATUS_CODES:
                body = " ".join(response.text.strip().split())
                last_error = NIMError(f"NIM HTTP {response.status_code}: {body[:500]}")
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_RETRY_DELAY_SECONDS)
                    continue
                raise last_error

            if response.status_code >= 400:
                body = " ".join(response.text.strip().split())
                raise NIMError(f"NIM HTTP {response.status_code}: {body[:500]}")

            try:
                data = response.json()
            except ValueError as exc:
                raise NIMError("NIM returned a non-JSON response") from exc

            return _extract_content(data)

        raise last_error or NIMError("NIM request failed")

    def close(self) -> None:
        self._session.close()
```

#### `repository.py`
```python
"""Repository for conversations and messages."""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timezone

from src.common.db import Database

logger = logging.getLogger(__name__)

class ConversationRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def get_conversation(self, conversation_id: UUID) -> Optional[Dict[str, Any]]:
        with self._db.transaction() as cursor:
            cursor.execute(
                "SELECT * FROM conversations WHERE id = %s",
                (str(conversation_id),)
            )
            return cursor.fetchone()

    def get_messages(self, conversation_id: UUID, limit: int = 50) -> List[Dict[str, Any]]:
        with self._db.transaction() as cursor:
            cursor.execute(
                "SELECT * FROM messages WHERE conversation_id = %s ORDER BY created_at ASC LIMIT %s",
                (str(conversation_id), limit)
            )
            return cursor.fetchall()

    def create_assistant_message(
        self,
        conversation_id: UUID,
        content: str,
        metadata: Optional[dict] = None
    ) -> UUID:
        with self._db.transaction() as cursor:
            cursor.execute(
                """INSERT INTO messages (conversation_id, role, content, metadata, created_at)
                   VALUES (%s, 'assistant', %s, %s, %s)
                   RETURNING id""",
                (str(conversation_id), content, metadata or {}, datetime.now(timezone.utc))
            )
            row = cursor.fetchone()
            return UUID(row["id"])

    def update_conversation_timestamp(self, conversation_id: UUID) -> None:
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE conversations SET updated_at = %s WHERE id = %s",
                (datetime.now(timezone.utc), str(conversation_id))
            )
```

#### `listener.py`
```python
"""Redis stream consumer using XREADGROUP."""
import logging
import json
from typing import Optional, List
from uuid import UUID

import redis
from pydantic import ValidationError

from src.config import LLMServerConfig
from src.models import ConversationMessage

logger = logging.getLogger(__name__)

class StreamListener:
    def __init__(self, config: LLMServerConfig, redis_client: redis.Redis):
        self.config = config
        self.redis = redis_client
        self.stream_key = config.input_stream
        self.group = config.consumer_group
        self.consumer = config.consumer_name

    def ensure_group(self) -> None:
        try:
            self.redis.xgroup_create(
                self.stream_key, self.group, id="0", mkstream=True
            )
            logger.info("Created consumer group %r on stream %r", self.group, self.stream_key)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
            logger.debug("Consumer group %r already exists", self.group)

    def read_messages(self, count: int = 10) -> List[ConversationMessage]:
        try:
            results = self.redis.xreadgroup(
                self.group,
                self.consumer,
                {self.stream_key: ">"},
                count=count,
                block=self.config.read_block_ms,
            )
        except redis.RedisError as e:
            logger.warning("XREADGROUP failed: %s", e)
            return []

        messages = []
        for stream_name, entries in results:
            for entry_id, data in entries:
                try:
                    # Sequin puts the row data in the stream
                    # Extract the payload (may need adjustment based on Sequin format)
                    payload = {k: v for k, v in data.items() if k != "id"}
                    msg = ConversationMessage(**payload)
                    msg._stream_entry_id = entry_id  # Store for ACK
                    messages.append(msg)
                except (ValidationError, KeyError) as e:
                    logger.warning("Failed to parse stream message: %s", e)
                    # ACK malformed messages to avoid blocking
                    self.redis.xack(self.stream_key, self.group, entry_id)
        return messages

    def ack(self, entry_id: str) -> None:
        try:
            self.redis.xack(self.stream_key, self.group, entry_id)
        except redis.RedisError as e:
            logger.warning("XACK failed for %s: %s", entry_id, e)

    def claim_stale(self, min_idle_time_ms: int = None) -> List[ConversationMessage]:
        min_idle = min_idle_time_ms or self.config.claim_idle_ms
        try:
            entries = self.redis.xautoclaim(
                self.stream_key,
                self.group,
                self.consumer,
                min_idle_time=min_idle,
                start_id="0-0",
                count=100,
            )
        except redis.RedisError as e:
            logger.warning("XAUTOCLAIM failed: %s", e)
            return []

        messages = []
        for entry_id, data in entries:
            try:
                payload = {k: v for k, v in data.items() if k != "id"}
                msg = ConversationMessage(**payload)
                msg._stream_entry_id = entry_id
                messages.append(msg)
            except (ValidationError, KeyError) as e:
                logger.warning("Failed to parse claimed message: %s", e)
                self.redis.xack(self.stream_key, self.group, entry_id)
        return messages
```

#### `processor.py`
```python
"""LLM message processor."""
import logging
import time
from typing import List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from src.config import LLMServerConfig
from src.nim_client import NIMClient, NIMError
from src.repository import ConversationRepository
from src.common.db import Database
from src.models import ConversationMessage, LLMResponse

logger = logging.getLogger(__name__)

class LLMProcessor:
    def __init__(
        self,
        config: LLMServerConfig,
        nim_client: NIMClient,
        repo: ConversationRepository,
        redis_client
    ):
        self.config = config
        self.nim = nim_client
        self.repo = repo
        self.redis = redis_client

    def process(self, msg: ConversationMessage) -> LLMResponse:
        logger.info("Processing message %s for conversation %s", msg.message_id, msg.conversation_id)
        started = time.monotonic()

        try:
            # Get conversation history
            history = self.repo.get_messages(msg.conversation_id, limit=20)
            
            # Build messages for NIM (include system prompt + history + current message)
            messages = [{"role": "system", "content": "You are a helpful assistant."}]
            for h in history:
                messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": msg.role, "content": msg.content})

            # Call NIM
            response_text = self.nim.chat(messages)
            latency_ms = int((time.monotonic() - started) * 1000)

            # Save assistant message to DB
            assistant_msg_id = self.repo.create_assistant_message(
                msg.conversation_id,
                response_text,
                metadata={"parent_message_id": str(msg.message_id), "latency_ms": latency_ms}
            )

            # Update conversation timestamp
            self.repo.update_conversation_timestamp(msg.conversation_id)

            return LLMResponse(
                conversation_id=msg.conversation_id,
                message_id=assistant_msg_id,
                response_content=response_text,
                latency_ms=latency_ms,
                status="completed",
            )

        except NIMError as e:
            latency_ms = int((time.monotonic() - started) * 1000)
            logger.error("NIM error for conversation %s: %s", msg.conversation_id, e)
            return LLMResponse(
                conversation_id=msg.conversation_id,
                message_id=UUID(int=0),  # Placeholder
                response_content="",
                latency_ms=latency_ms,
                status="failed",
                error=str(e)
            )
        except Exception as e:
            latency_ms = int((time.monotonic() - started) * 1000)
            logger.exception("Unexpected error processing message %s", msg.message_id)
            return LLMResponse(
                conversation_id=msg.conversation_id,
                message_id=UUID(int=0),
                response_content="",
                latency_ms=latency_ms,
                status="failed",
                error=f"{type(e).__name__}: {e}"
            )

    def publish_response(self, response: LLMResponse) -> None:
        """Publish response to output stream for Sequin/main server."""
        try:
            self.redis.xadd(
                self.config.output_stream,
                {
                    "conversation_id": str(response.conversation_id),
                    "message_id": str(response.message_id),
                    "response_content": response.response_content,
                    "latency_ms": str(response.latency_ms),
                    "status": response.status,
                    "error": response.error or "",
                },
                maxlen=self.config.stream_maxlen,
                approximate=True,
            )
            logger.debug("Published response for conversation %s", response.conversation_id)
        except Exception as e:
            logger.warning("Failed to publish response to stream: %s", e)
```

#### `main.py`
```python
"""Entry point for LLM Server."""
import logging
import signal
import sys
import threading
import time

from dotenv import load_dotenv

from src.config import LLMServerConfig
from src.listener import StreamListener
from src.processor import LLMProcessor
from src.nim_client import NIMClient
from src.repository import ConversationRepository
from src.common.db import Database
from src.common.redis import create_redis_client

load_dotenv()
load_dotenv(".env.local", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("llm_server")

class LLMServer:
    def __init__(self):
        self.config = LLMServerConfig.from_env()
        self._running = False
        self._threads = []

    def start(self):
        logger.info("Starting LLM Server...")
        
        # Initialize connections
        db = Database(self.config.database_url)
        redis_client = create_redis_client(self.config.redis_url)
        
        # Initialize components
        api_keys = self.config.load_api_keys()
        nim_client = NIMClient(
            api_keys=api_keys,
            base_url=self.config.base_url,
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout_seconds=self.config.timeout_seconds,
        )
        
        repo = ConversationRepository(db)
        listener = StreamListener(self.config, redis_client)
        processor = LLMProcessor(self.config, nim_client, repo, redis_client)
        
        # Ensure consumer group exists
        listener.ensure_group()
        
        self._running = True
        
        # Start worker threads
        for i in range(self.config.max_concurrent_jobs):
            thread = threading.Thread(
                target=self._worker_loop,
                args=(listener, processor),
                name=f"llm-worker-{i}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)
        
        logger.info("Started %d worker threads", self.config.max_concurrent_jobs)
        
        # Main loop - just keep alive and handle stale claim
        try:
            while self._running:
                time.sleep(30)
                # Periodic stale claim
                claimed = listener.claim_stale()
                for msg in claimed:
                    logger.info("Reclaimed stale message %s", msg.message_id)
                    # Process in background (could use a queue)
                    threading.Thread(
                        target=self._process_and_ack,
                        args=(listener, processor, msg),
                        daemon=True
                    ).start()
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            self.stop()
            nim_client.close()
            redis_client.close()
            db.close()
            logger.info("LLM Server stopped")

    def _worker_loop(self, listener: StreamListener, processor: LLMProcessor):
        while self._running:
            try:
                messages = listener.read_messages(count=1)
                for msg in messages:
                    self._process_and_ack(listener, processor, msg)
            except Exception as e:
                logger.exception("Worker error: %s", e)
                time.sleep(5)  # Back off on error

    def _process_and_ack(self, listener: StreamListener, processor: LLMProcessor, msg: ConversationMessage):
        entry_id = getattr(msg, "_stream_entry_id", None)
        try:
            response = processor.process(msg)
            processor.publish_response(response)
        finally:
            if entry_id:
                listener.ack(entry_id)

    def stop(self):
        self._running = False
        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=10)

def main():
    server = LLMServer()
    
    def signal_handler(signum, frame):
        logger.info("Received signal %s", signum)
        server.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    server.start()

if __name__ == "__main__":
    main()
```

### Phase 3: Docker Configuration

#### `Dockerfile`
```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# CA certs for HTTPS
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src

RUN useradd --create-home --uid 1000 worker \
    && chown -R worker:worker /app
USER worker

# The nim.txt key file will be mounted at runtime
CMD ["python", "-m", "src.main"]
```

#### `.env.example`
```bash
# PostgreSQL (required)
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/mugiko

# Redis
REDIS_URL=redis://redis:6379/0

# Stream consumption
LLM_CONSUMER_GROUP=llm-workers
LLM_CONSUMER_NAME=worker-1
LLM_INPUT_STREAM=conversation_messages
LLM_OUTPUT_STREAM=llm_responses
LLM_READ_BLOCK_MS=5000
LLM_CLAIM_IDLE_MS=300000
LLM_STREAM_MAXLEN=10000

# NVIDIA NIM
NVIDIA_API_KEYS_FILE=nim.txt
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_NIM_MODEL=deepseek-ai/deepseek-v4.1-flash
NVIDIA_NIM_TEMPERATURE=0.2
NVIDIA_NIM_MAX_TOKENS=4096
NVIDIA_NIM_TIMEOUT_SECONDS=120

# Processing
LLM_POLL_INTERVAL_MS=2000
LLM_MAX_CONCURRENT_JOBS=10
```

### Phase 4: Docker Compose Updates

Add to `/c/Projects/MugikoWorkServer/doc/docker-compose.yml`:
```yaml
  llm_server:
    build:
      context: /c/Projects/llm_server
      dockerfile: Dockerfile
    container_name: mugiko_llm_server
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/mugiko
      - REDIS_URL=redis://sequin_redis:6379/0
      - NVIDIA_API_KEYS_FILE=/app/nim.txt
      # Other vars from .env.example
    volumes:
      - ./nim.txt:/app/nim.txt:ro  # Mount keys file read-only
    depends_on:
      sequin_redis:
        condition: service_started
      postgres:
        condition: service_healthy
    # Run on same network as other services
```

### Phase 5: Sequin Configuration

Create/update `/c/Projects/MugikoWorkServer/doc/playground.yml`:
```yaml
# Sequin configuration to watch conversations/messages tables
tables:
  - name: conversations
    schema: public
    primary_keys: [id]
    columns:
      - id
      - user_id
      - title
      - created_at
      - updated_at
    stream:
      name: conversation_changes
      keys: [id]
  
  - name: messages
    schema: public
    primary_keys: [id]
    columns:
      - id
      - conversation_id
      - role
      - content
      - metadata
      - created_at
    stream:
      name: conversation_messages
      keys: [conversation_id]  # Partition by conversation
```

### Phase 6: Main Server (MugikoGO) Integration

The main server needs:
1. API endpoints to create conversations and send messages
2. SSE endpoint to listen to `llm_responses` stream
3. When user sends message → insert into `messages` table → Sequin → Redis → LLM Server

---

## Implementation Order

1. **Create `/c/Projects/llm_server` with all source files**
2. **Add conversation/message tables to `doc/schema.sql`** (run migration)
3. **Create `playground.yml` for Sequin** 
4. **Update `docker-compose.yml` to include `llm_server` service**
5. **Build and test the LLM server**
6. **Integrate with MugikoGO API (conversation endpoints + SSE)**

---

## Key Design Decisions

1. **Separate LLM Server**: Runs as independent Python process, scales independently
2. **Redis Streams**: At-least-once delivery via consumer groups, automatic reclaim
3. **Sequin as CDC**: No direct DB polling, uses PostgreSQL logical replication
4. **NVIDIA NIM**: Uses existing key rotation and retry logic from MugikoWorkServer
5. **Stateless Workers**: Each worker thread processes independently, no shared state
6. **DB as Source of Truth**: All conversation state in PostgreSQL, streams are notifications only

---

## Testing Checklist

- [ ] LLM server starts and connects to PostgreSQL/Redis
- [ ] Consumer group created on `conversation_messages` stream
- [ ] Insert message into `messages` table → appears in Redis stream
- [ ] LLM server processes message, calls NIM, writes response
- [ ] Response appears in `llm_responses` stream
- [ ] Main server SSE receives response
- [ ] Stale message reclaim works (kill worker mid-processing)
- [ ] Multiple workers process in parallel
- [ ] Error handling: NIM failure, DB failure, Redis failure