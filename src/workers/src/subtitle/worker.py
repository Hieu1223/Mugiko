"""Subtitle worker: Redis stream consumption and job orchestration.

``run(queue)`` is the only public entrypoint. It performs the startup
registry sync, joins the consumer group, then blocks reading the stream.
Provider/processor/persistence calls happen only from here.
"""

import logging
import time
import uuid
from typing import Any, Mapping, Optional

import redis
from redis.exceptions import ResponseError

from .config import SubtitleConfig
from .persistent.db import Database
from .persistent.registry_sync import sync_registry
from .persistent.subtitle_repo import SubtitleRepository
from .processor.json3 import json3_to_segments
from .provider import get_provider, get_providers
from .provider.youtube import NoSubtitlesAvailable
from .status_stream import SubtitleStatusPublisher

logger = logging.getLogger(__name__)

_RECONNECT_DELAY_SECONDS = 5


def run(queue: str) -> None:
    """Blocking consumer loop for one Redis stream key.

    The loop is intentionally endless: startup failures (database/Redis not
    ready) and runtime infrastructure failures are logged and retried instead
    of terminating the worker. Configuration errors (e.g. a missing
    ``DATABASE_URL``) still fail fast.
    """
    if not isinstance(queue, str) or not queue:
        raise ValueError("queue must be a non-empty Redis stream key")

    config = SubtitleConfig.from_env()

    while True:
        try:
            _serve(queue, config)
        except Exception:
            logger.exception(
                "Subtitle worker on stream %r stopped unexpectedly; "
                "reconnecting in %d seconds",
                queue,
                _RECONNECT_DELAY_SECONDS,
            )
        else:
            logger.warning(
                "Subtitle worker on stream %r exited; restarting in %d seconds",
                queue,
                _RECONNECT_DELAY_SECONDS,
            )
        time.sleep(_RECONNECT_DELAY_SECONDS)


def _serve(queue: str, config: SubtitleConfig) -> None:
    """One connection lifetime; returns/raises when it must be rebuilt."""
    db = Database(config.database_url)
    client = None

    try:
        client = redis.Redis.from_url(config.redis_url, decode_responses=True)
        repo = SubtitleRepository(db)
        publisher = SubtitleStatusPublisher(
            client,
            config.status_stream,
            config.status_stream_maxlen,
        )

        sync_registry(db, get_providers())
        _ensure_group(client, queue, config.consumer_group)
        _drain_pending(
            client,
            queue,
            config.consumer_group,
            config.consumer_name,
            config.claim_idle_ms,
            repo,
            publisher,
        )

        logger.info(
            "Waiting for messages: stream=%r group=%r consumer=%r",
            queue,
            config.consumer_group,
            config.consumer_name,
        )

        while True:
            try:
                response = client.xreadgroup(
                    config.consumer_group,
                    config.consumer_name,
                    {queue: ">"},
                    count=1,
                    block=config.read_block_ms,
                )
            except redis.RedisError:
                logger.exception("Redis read failed; retrying in 1 second")
                time.sleep(1)
                continue

            if not response:
                _drain_pending(
                    client,
                    queue,
                    config.consumer_group,
                    config.consumer_name,
                    config.claim_idle_ms,
                    repo,
                    publisher,
                )
                continue

            for _stream_name, messages in response:
                for message_id, fields in messages:
                    _handle_message(
                        client,
                        queue,
                        config.consumer_group,
                        message_id,
                        fields,
                        repo,
                        publisher,
                    )
    finally:
        if client is not None:
            client.close()
        db.close()
        logger.info("Subtitle worker connection on stream %r closed", queue)


def _ensure_group(client: redis.Redis, stream_key: str, group: str) -> None:
    try:
        client.xgroup_create(stream_key, group, id="0-0", mkstream=True)
        logger.info("Created consumer group %r on stream %r", group, stream_key)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise
        logger.info(
            "Consumer group %r already exists on stream %r",
            group,
            stream_key,
        )


def _drain_pending(
    client: redis.Redis,
    stream_key: str,
    group: str,
    consumer: str,
    claim_idle_ms: int,
    repo: SubtitleRepository,
    publisher: SubtitleStatusPublisher,
) -> None:
    """Reclaim messages left pending by crashed or stopped consumers."""
    start_id = "0-0"
    while True:
        try:
            result = client.xautoclaim(
                stream_key,
                group,
                consumer,
                min_idle_time=claim_idle_ms,
                start_id=start_id,
                count=50,
            )
        except redis.RedisError:
            logger.exception("Pending reclaim failed; reconnecting")
            raise

        next_id = result[0]
        messages = result[1]
        for message_id, fields in messages:
            _handle_message(
                client,
                stream_key,
                group,
                message_id,
                fields,
                repo,
                publisher,
            )

        if not messages or next_id == "0-0":
            return
        start_id = next_id


def _handle_message(
    client: redis.Redis,
    stream_key: str,
    group: str,
    message_id: str,
    fields: Mapping[str, Any],
    repo: SubtitleRepository,
    publisher: SubtitleStatusPublisher,
) -> None:
    logger.info("Received %s[%s]: %s", stream_key, message_id, fields)

    try:
        _process_job(fields, repo, publisher)
    except Exception:
        # Infrastructure failure (DB down, unexpected persistence error):
        # leave the message pending and force a reconnect so the next attempt
        # uses a fresh connection.
        logger.exception(
            "Handling message %s did not finish — reconnecting; "
            "message remains pending for recovery",
            message_id,
        )
        raise

    try:
        client.xack(stream_key, group, message_id)
    except redis.RedisError:
        logger.exception(
            "Could not acknowledge message %s — reconnecting; "
            "message remains pending",
            message_id,
        )
        raise


def _validated_uuid(raw: Any) -> Optional[str]:
    if not raw:
        return None
    try:
        return str(uuid.UUID(str(raw)))
    except (TypeError, ValueError, AttributeError):
        return None


def _mark_failed(
    repo: SubtitleRepository,
    publisher: SubtitleStatusPublisher,
    subtitle_id: str,
) -> None:
    repo.mark_failed(subtitle_id)
    publisher.publish(subtitle_id, "failed")


def _process_job(
    fields: Mapping[str, Any],
    repo: SubtitleRepository,
    publisher: SubtitleStatusPublisher,
) -> None:
    """Process one message; job-level failures are recorded and acknowledged."""
    subtitle_id = _validated_uuid(fields.get("id"))
    provider_name = fields.get("provider")
    service_key = fields.get("service")
    video_url = fields.get("video_url")

    if (
        subtitle_id is None
        or not provider_name
        or not service_key
        or not video_url
    ):
        logger.error("Dropping malformed message: %s", dict(fields))
        return

    logger.info(
        "Job %s: provider=%s service=%s url=%s",
        subtitle_id,
        provider_name,
        service_key,
        video_url,
    )

    status = repo.get_status(subtitle_id)
    if status is None:
        logger.error(
            "No subtitles row with id %s — message dropped",
            subtitle_id,
        )
        return
    if status == "completed":
        logger.info(
            "Job %s already completed — skipping redelivery",
            subtitle_id,
        )
        return

    provider_info = get_provider(provider_name)
    if provider_info is None:
        logger.warning(
            "No registered provider '%s' — marking job %s failed",
            provider_name,
            subtitle_id,
        )
        _mark_failed(repo, publisher, subtitle_id)
        return

    service_info = provider_info.get_service(service_key)
    if service_info is None:
        logger.warning(
            "Provider '%s' has no service '%s' — marking job %s failed",
            provider_name,
            service_key,
            subtitle_id,
        )
        _mark_failed(repo, publisher, subtitle_id)
        return

    repo.set_status(subtitle_id, "processing")
    publisher.publish(subtitle_id, "processing")

    try:
        artifact = service_info.func(provider_info.cls(), video_url)
    except NoSubtitlesAvailable as exc:
        logger.warning("Job %s: %s", subtitle_id, exc)
        _mark_failed(repo, publisher, subtitle_id)
        return
    except Exception:
        logger.exception("Job %s: provider failed", subtitle_id)
        _mark_failed(repo, publisher, subtitle_id)
        return

    try:
        segments = json3_to_segments(
            artifact["raw"],
            artifact.get("language", "ja"),
        )
    except Exception:
        logger.exception("Job %s: processing failed", subtitle_id)
        _mark_failed(repo, publisher, subtitle_id)
        return

    if not segments:
        logger.warning(
            "Job %s: subtitle track produced no segments — marking failed",
            subtitle_id,
        )
        _mark_failed(repo, publisher, subtitle_id)
        return

    repo.save_result(subtitle_id, segments)
    publisher.publish(subtitle_id, "completed")
    logger.info(
        "Job %s completed with %d segment(s)",
        subtitle_id,
        len(segments),
    )
