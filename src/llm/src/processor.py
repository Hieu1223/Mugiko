"""LLM message processor."""
import logging
import time
from typing import List, Dict, Any, Union
from uuid import UUID
from datetime import datetime, timezone

from src.config import LLMServerConfig
from src.nim_client import NIMClient, NIMError
from src.repository import ConversationRepository
from src.common.db import Database
from src.models import ConversationMessage, LLMResponse, LLMJobMessage, LLMJobResponse

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
        self.db = repo._db

    def process(self, msg: Union[ConversationMessage, LLMJobMessage]) -> Union[LLMResponse, LLMJobResponse]:
        if isinstance(msg, LLMJobMessage):
            return self._process_job(msg)
        return self._process_conversation(msg)

    def _process_conversation(self, msg: ConversationMessage) -> LLMResponse:
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

    def _process_job(self, msg: LLMJobMessage) -> LLMJobResponse:
        logger.info("Processing job %s", msg.id)
        started = time.monotonic()

        # Check current job status first - only process queued jobs
        with self.db.transaction() as cursor:
            cursor.execute("SELECT status FROM llm_jobs WHERE id = %s", (str(msg.id),))
            row = cursor.fetchone()
            if not row:
                logger.warning("Job %s not found in database", msg.id)
                return LLMJobResponse(
                    job_id=msg.id,
                    response="",
                    latency_ms=0,
                    status="failed",
                    error="Job not found"
                )
            current_status = row["status"]
            if current_status != "queued":
                logger.info("Job %s already %s, skipping", msg.id, current_status)
                return LLMJobResponse(
                    job_id=msg.id,
                    response="",
                    latency_ms=0,
                    status=current_status,
                    error=None if current_status == "completed" else "Already processed"
                )

        try:
            # Model is server-controlled; never accept a model from the message

            # Build messages for NIM
            messages = [{"role": "system", "content": "You are a helpful assistant."}]
            if msg.conversation_id:
                history = self.repo.get_messages(msg.conversation_id, limit=20)
                for h in history:
                    messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": msg.prompt})

            # Call NIM
            response_text = self.nim.chat(messages)
            latency_ms = int((time.monotonic() - started) * 1000)

            # Update job in database
            with self.db.transaction() as cursor:
                cursor.execute(
                    """UPDATE llm_jobs 
                       SET response = %s, status = 'completed', updated_at = %s
                       WHERE id = %s""",
                    (response_text, datetime.now(timezone.utc), str(msg.id))
                )

            # If there's a conversation_id, also save as assistant message
            if msg.conversation_id:
                self.repo.create_assistant_message(
                    msg.conversation_id,
                    response_text,
                    metadata={"parent_message_id": str(msg.id), "latency_ms": latency_ms, "job_id": str(msg.id)}
                )
                self.repo.update_conversation_timestamp(msg.conversation_id)

            return LLMJobResponse(
                job_id=msg.id,
                response=response_text,
                latency_ms=latency_ms,
                status="completed",
            )

        except NIMError as e:
            latency_ms = int((time.monotonic() - started) * 1000)
            logger.error("NIM error for job %s: %s", msg.id, e)
            with self.db.transaction() as cursor:
                cursor.execute(
                    """UPDATE llm_jobs 
                       SET error = %s, status = 'failed', updated_at = %s
                       WHERE id = %s""",
                    (str(e), datetime.now(timezone.utc), str(msg.id))
                )
            return LLMJobResponse(
                job_id=msg.id,
                response="",
                latency_ms=latency_ms,
                status="failed",
                error=str(e)
            )
        except Exception as e:
            latency_ms = int((time.monotonic() - started) * 1000)
            logger.exception("Unexpected error processing job %s", msg.id)
            with self.db.transaction() as cursor:
                cursor.execute(
                    """UPDATE llm_jobs 
                       SET error = %s, status = 'failed', updated_at = %s
                       WHERE id = %s""",
                    (f"{type(e).__name__}: {e}", datetime.now(timezone.utc), str(msg.id))
                )
            return LLMJobResponse(
                job_id=msg.id,
                response="",
                latency_ms=latency_ms,
                status="failed",
                error=f"{type(e).__name__}: {e}"
            )

    def publish_response(self, response: Union[LLMResponse, LLMJobResponse]) -> None:
        """Publish response to output stream for Sequin/main server."""
        try:
            if isinstance(response, LLMJobResponse):
                self.redis.xadd(
                    self.config.output_stream,
                    {
                        "job_id": str(response.job_id),
                        "response": response.response,
                        "latency_ms": str(response.latency_ms),
                        "status": response.status,
                        "error": response.error or "",
                    },
                    maxlen=self.config.stream_maxlen,
                    approximate=True,
                )
                logger.debug("Published job response for job %s", response.job_id)
            else:
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