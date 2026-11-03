"""Redis connection helpers."""

import logging
import redis

logger = logging.getLogger(__name__)


def create_redis_client(redis_url: str) -> redis.Redis:
    """Create a Redis client with sensible defaults."""
    client = redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_keepalive=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    # Test connection
    try:
        client.ping()
        logger.info("Connected to Redis at %s", redis_url)
    except redis.RedisError as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise
    return client