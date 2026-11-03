"""PostgreSQL plumbing shared by worker modules."""

import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class Database:
    """A single long-lived PostgreSQL connection with transaction helpers."""

    def __init__(self, database_url: str) -> None:
        self._conn = psycopg2.connect(database_url)
        self._conn.autocommit = False
        logger.info("Connected to PostgreSQL")

    @contextmanager
    def transaction(self):
        """Yield a real-dict cursor; commit on success, roll back on error."""
        cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cursor
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            cursor.close()

    def close(self) -> None:
        self._conn.close()
