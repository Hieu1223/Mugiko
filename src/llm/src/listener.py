"""Redis stream consumer using XREADGROUP."""
import logging
import json
from typing import Optional, List, Union
from uuid import UUID

import redis
from pydantic import ValidationError

from src.config import LLMServerConfig
from src.models import ConversationMessage, LLMJobMessage

logger = logging.getLogger(__name__)


class StreamListener:
    def __init__(self, config: LLMServerConfig, redis_client: redis.Redis):
        self.config = config
        self.redis = redis_client
        self.stream_key = config.input_stream
        self.jobs_stream_key = config.jobs_stream
        self.group = config.consumer_group
        self.consumer = config.consumer_name

    def ensure_group(self) -> None:
        # Ensure group for conversation_messages stream
        try:
            self.redis.xgroup_create(
                self.stream_key, self.group, id="0", mkstream=True
            )
            logger.info("Created consumer group %r on stream %r", self.group, self.stream_key)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
            logger.debug("Consumer group %r already exists on stream %r", self.group, self.stream_key)

        # Ensure group for llm_jobs stream
        try:
            self.redis.xgroup_create(
                self.jobs_stream_key, self.group, id="0", mkstream=True
            )
            logger.info("Created consumer group %r on stream %r", self.group, self.jobs_stream_key)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
            logger.debug("Consumer group %r already exists on stream %r", self.group, self.jobs_stream_key)

    def read_messages(self, count: int = 10) -> List[Union[ConversationMessage, LLMJobMessage]]:
        try:
            results = self.redis.xreadgroup(
                self.group,
                self.consumer,
                {self.stream_key: ">", self.jobs_stream_key: ">"},
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
                    # Sequin stream format: record, metadata, action, changes
                    # The actual message data is in the 'record' field as JSON
                    if "record" in data:
                        import json
                        record_data = json.loads(data["record"])
                        # Add metadata fields
                        if "metadata" in data:
                            meta = json.loads(data["metadata"])
                            record_data["_sequin_metadata"] = meta
                        
                        # Parse based on stream AND table_name in metadata
                        # llm_jobs stream always has LLMJobMessage records
                        # conversation_messages stream can have Conversation or Message records
                        if stream_name == self.jobs_stream_key:
                            msg = LLMJobMessage(**record_data)
                        else:
                            # Check table_name to determine message type
                            table_name = meta.get("table_name") if "metadata" in data else None
                            if table_name == "messages":
                                msg = ConversationMessage(**record_data)
                            elif table_name == "conversations":
                                # Skip conversation records on this stream - they're not messages
                                logger.debug("Skipping conversation record on messages stream")
                                self.redis.xack(stream_name, self.group, entry_id)
                                continue
                            else:
                                # Fallback: try ConversationMessage
                                msg = ConversationMessage(**record_data)
                    else:
                        # Fallback: try direct parsing
                        payload = {k: v for k, v in data.items() if k != "id"}
                        if stream_name == self.jobs_stream_key:
                            msg = LLMJobMessage(**payload)
                        else:
                            msg = ConversationMessage(**payload)
                    msg._stream_entry_id = entry_id  # Store for ACK
                    msg._stream_name = stream_name
                    messages.append(msg)
                except (ValidationError, KeyError, json.JSONDecodeError) as e:
                    logger.warning("Failed to parse stream message: %s", e)
                    # ACK malformed messages to avoid blocking
                    self.redis.xack(stream_name, self.group, entry_id)
        return messages

    def ack(self, entry_id: str, stream_name: str = None) -> None:
        stream = stream_name or self.stream_key
        try:
            self.redis.xack(stream, self.group, entry_id)
        except redis.RedisError as e:
            logger.warning("XACK failed for %s on %s: %s", entry_id, stream, e)

    def claim_stale(self, min_idle_time_ms: int = None) -> List[Union[ConversationMessage, LLMJobMessage]]:
        min_idle = min_idle_time_ms or self.config.claim_idle_ms
        messages = []
        
        for stream_name in [self.stream_key, self.jobs_stream_key]:
            try:
                next_id, entries, deleted_ids = self.redis.xautoclaim(
                    stream_name,
                    self.group,
                    self.consumer,
                    min_idle_time=min_idle,
                    start_id="0-0",
                    count=100,
                )
            except redis.RedisError as e:
                logger.warning("XAUTOCLAIM failed for %s: %s", stream_name, e)
                continue

            for entry_id, data in entries:
                try:
                    if "record" in data:
                        import json
                        record_data = json.loads(data["record"])
                        if "metadata" in data:
                            meta = json.loads(data["metadata"])
                            record_data["_sequin_metadata"] = meta
                        
                        if stream_name == self.jobs_stream_key:
                            msg = LLMJobMessage(**record_data)
                        else:
                            # Check table_name to determine message type
                            table_name = meta.get("table_name")
                            if table_name == "messages":
                                msg = ConversationMessage(**record_data)
                            elif table_name == "conversations":
                                # Skip conversation records on this stream - they're not messages
                                logger.debug("Skipping conversation record on messages stream")
                                self.redis.xack(stream_name, self.group, entry_id)
                                continue
                            else:
                                # Fallback: try ConversationMessage
                                msg = ConversationMessage(**record_data)
                    else:
                        payload = {k: v for k, v in data.items() if k != "id"}
                        if stream_name == self.jobs_stream_key:
                            msg = LLMJobMessage(**payload)
                        else:
                            msg = ConversationMessage(**payload)
                    msg._stream_entry_id = entry_id
                    msg._stream_name = stream_name
                    messages.append(msg)
                except (ValidationError, KeyError, json.JSONDecodeError) as e:
                    logger.warning("Failed to parse claimed message: %s", e)
                    self.redis.xack(stream_name, self.group, entry_id)
        return messages