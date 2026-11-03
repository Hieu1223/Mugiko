"""Best-effort publisher for job status changes.

The API layer listens to status streams and forwards matching entries to
clients as Server-Sent Events. Publishing is deliberately best-effort: the
database is the source of truth, and a Redis outage must not fail or wedge a
worker job.
"""

import logging

import redis

logger = logging.getLogger(__name__)


class StatusPublisher:
    """Publish ``{id, status}`` updates to a Redis stream."""

    def __init__(
        self,
        client: redis.Redis,
        stream_key: str,
        maxlen: int = 10_000,
    ) -> None:
        self._client = client
        self._stream_key = stream_key
        self._maxlen = maxlen

    def publish(self, entity_id: str, status: str) -> None:
        try:
            self._client.xadd(
                self._stream_key,
                {"id": entity_id, "status": status},
                maxlen=self._maxlen,
                approximate=True,
            )
        except redis.RedisError:
            logger.warning(
                "Could not publish status %r for %s to stream %r",
                status,
                entity_id,
                self._stream_key,
                exc_info=True,
            )
