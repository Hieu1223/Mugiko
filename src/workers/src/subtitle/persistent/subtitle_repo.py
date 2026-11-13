"""Repository for the subtitle module tables (doc/schema.sql)."""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import psycopg2.extras

from .db import Database

logger = logging.getLogger(__name__)

# Rows eligible for recovery: stuck in queued/processing after a silence
# period. "failed" is intentionally terminal so permanently failing jobs
# (e.g. a video with no subtitle track) are not retried endlessly.
_STALE_STATUSES = ("queued", "processing")


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
        language: Optional[str] = None,
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
                "SET status = 'completed', "
                "    language = COALESCE(%s, language), "
                "    updated_at = NOW() "
                "WHERE id = %s",
                (language, subtitle_id),
            )

        logger.info(
            "Persisted %d segment(s) for subtitle %s",
            len(values),
            subtitle_id,
        )

    def claim_stale_jobs(
        self, stale_after_seconds: int, limit: int
    ) -> List[Dict[str, Any]]:
        """Claim stuck subtitle rows so another worker can retry them.

        Selects rows in ``queued``/``processing`` older than
        ``stale_after_seconds`` seconds, marks them ``processing`` atomically
        (``FOR UPDATE SKIP LOCKED``), and returns them with provider/service
        keys so the worker can rebuild the job message and rerun it.

        ``failed`` rows are intentionally skipped — they are terminal.
        """
        if limit <= 0:
            return []

        placeholders = ",".join(["%s"] * len(_STALE_STATUSES))
        with self._db.transaction() as cursor:
            cursor.execute(
                f"""
                WITH locked AS (
                    SELECT s.id
                    FROM subtitles s
                    WHERE s.status IN ({placeholders})
                      AND s.updated_at < NOW() - (%s || ' seconds')::interval
                    ORDER BY s.updated_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT %s
                ),
                updated AS (
                    UPDATE subtitles s
                    SET status = 'processing', updated_at = NOW()
                    WHERE s.id IN (SELECT id FROM locked)
                    RETURNING s.id, s.video_url, s.provider_id, s.service_id
                )
                SELECT u.id AS subtitle_id,
                       u.video_url,
                       p.name  AS provider_name,
                       sv.service_key
                FROM updated u
                JOIN subtitle_providers p ON p.id = u.provider_id
                JOIN subtitle_provider_services sv
                  ON sv.id = u.service_id AND sv.provider_id = u.provider_id
                """,
                list(_STALE_STATUSES) + [str(stale_after_seconds), limit],
            )
            rows = [dict(row) for row in cursor.fetchall()]

        if rows:
            logger.info(
                "Recovered %d stale subtitle job(s)", len(rows),
            )
        return rows
