"""Repository for the ``llm_jobs`` table."""

import logging
from typing import Any, Dict, List, Optional

from src.common.db import Database

logger = logging.getLogger(__name__)


class LLMJobRepository:
    """Claim queued jobs and record their terminal state."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def claim_next(self) -> Optional[Dict[str, Any]]:
        """Atomically claim the oldest queued job, or return None."""
        with self._db.transaction() as cursor:
            cursor.execute(
                "SELECT id, prompt FROM llm_jobs "
                "WHERE status = 'queued' "
                "ORDER BY created_at "
                "LIMIT 1 "
                "FOR UPDATE SKIP LOCKED"
            )
            row = cursor.fetchone()
            if row is None:
                return None

            cursor.execute(
                "UPDATE llm_jobs "
                "SET status = 'processing', error = NULL, updated_at = NOW() "
                "WHERE id = %s "
                "RETURNING id, prompt",
                (row["id"],),
            )
            return cursor.fetchone()

    def mark_completed(self, job_id: Any, response: str) -> None:
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE llm_jobs "
                "SET status = 'completed', response = %s, error = NULL, "
                "    updated_at = NOW() "
                "WHERE id = %s",
                (response, job_id),
            )

    def mark_failed(self, job_id: Any, error: str) -> None:
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE llm_jobs "
                "SET status = 'failed', error = %s, updated_at = NOW() "
                "WHERE id = %s",
                (error, job_id),
            )

    def requeue_stale(self, stale_seconds: int) -> List[Any]:
        """Return ids of jobs stuck in processing for too long."""
        with self._db.transaction() as cursor:
            cursor.execute(
                "UPDATE llm_jobs "
                "SET status = 'queued', updated_at = NOW() "
                "WHERE status = 'processing' "
                "AND updated_at < NOW() - (%s * INTERVAL '1 second') "
                "RETURNING id",
                (stale_seconds,),
            )
            return [row["id"] for row in cursor.fetchall()]
