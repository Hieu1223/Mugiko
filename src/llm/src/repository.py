"""Repository for conversations and messages."""
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime, timezone

from psycopg2.extras import Json
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
        from uuid import uuid4
        msg_id = uuid4()
        with self._db.transaction() as cursor:
            cursor.execute(
                """INSERT INTO messages (id, conversation_id, role, content, metadata, created_at)
                   VALUES (%s, %s, 'assistant', %s, %s, %s)
                   RETURNING id""",
                (str(msg_id), str(conversation_id), content, Json(metadata or {}), datetime.now(timezone.utc))
            )
            row = cursor.fetchone()
            return UUID(row["id"])

    def update_conversation_timestamp(self, conversation_id: UUID) -> None:
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE conversations SET updated_at = %s WHERE id = %s",
                (datetime.now(timezone.utc), str(conversation_id))
            )