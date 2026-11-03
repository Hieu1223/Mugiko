"""Repository for the subtitle module tables (doc/schema.sql)."""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import psycopg2.extras

from .db import Database

logger = logging.getLogger(__name__)


class SubtitleRepository:
    """Status transitions and idempotent segment writes.

    ``save_result`` deletes previous segments and inserts the new set in the
    same transaction that marks the job completed, so redelivery can safely
    rerun a job that was interrupted halfway through.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    def get_status(self, subtitle_id: str) -> Optional[str]:
        with self._db.transaction() as cursor:
            cursor.execute(
                "SELECT status FROM subtitles WHERE id = %s",
                (subtitle_id,),
            )
            row = cursor.fetchone()
        return row["status"] if row else None

    def set_status(self, subtitle_id: str, status: str) -> None:
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE subtitles "
                "SET status = %s, updated_at = NOW() "
                "WHERE id = %s",
                (status, subtitle_id),
            )

    def mark_failed(self, subtitle_id: str) -> None:
        self.set_status(subtitle_id, "failed")

    def save_result(
        self,
        subtitle_id: str,
        segments: List[Dict[str, Any]],
    ) -> None:
        """Replace all segments for a job and mark it completed."""
        values = [
            (
                str(uuid.uuid4()),
                subtitle_id,
                segment["idx"],
                segment["start_ms"],
                segment["end_ms"],
                json.dumps(segment["words"]),
            )
            for segment in segments
        ]

        with self._db.transaction() as cursor:
            cursor.execute(
                "DELETE FROM subtitle_segments WHERE subtitle_id = %s",
                (subtitle_id,),
            )
            if values:
                psycopg2.extras.execute_values(
                    cursor,
                    "INSERT INTO subtitle_segments "
                    "(id, subtitle_id, idx, start_ms, end_ms, words) VALUES %s",
                    values,
                    template="(%s, %s, %s, %s, %s, %s::jsonb)",
                )
            cursor.execute(
                "UPDATE subtitles "
                "SET status = 'completed', updated_at = NOW() "
                "WHERE id = %s",
                (subtitle_id,),
            )

        logger.info(
            "Persisted %d segment(s) for subtitle %s",
            len(values),
            subtitle_id,
        )
