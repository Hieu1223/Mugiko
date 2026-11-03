"""Blocking worker for queued NVIDIA NIM LLM jobs."""

import logging
import time

import redis

from src.common.db import Database
from src.common.status_stream import StatusPublisher

from .config import LLMConfig
from .nim import NIMClient, NIMError
from .repository import LLMJobRepository

logger = logging.getLogger(__name__)

_RECONNECT_DELAY_SECONDS = 5
_STALE_SWEEP_INTERVAL_SECONDS = 60


def run() -> None:
    """Consume ``llm_jobs`` forever, reconnecting after infrastructure errors."""
    while True:
        try:
            _serve()
        except Exception:
            logger.exception(
                "LLM worker stopped unexpectedly; reconnecting in %d seconds",
                _RECONNECT_DELAY_SECONDS,
            )
        else:
            logger.warning(
                "LLM worker exited; restarting in %d seconds",
                _RECONNECT_DELAY_SECONDS,
            )
        time.sleep(_RECONNECT_DELAY_SECONDS)


def _serve() -> None:
    config = LLMConfig.from_env()
    api_keys = config.load_api_keys()
    logger.info(
        "LLM worker using %d NIM key(s), model=%s",
        len(api_keys),
        config.model,
    )

    db = Database(config.database_url)
    redis_client = redis.Redis.from_url(config.redis_url, decode_responses=True)
    publisher = StatusPublisher(
        redis_client,
        config.status_stream,
        config.status_stream_maxlen,
    )
    client = NIMClient(
        api_keys=api_keys,
        base_url=config.base_url,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        timeout_seconds=config.timeout_seconds,
    )

    try:
        repo = LLMJobRepository(db)
        last_sweep = 0.0

        while True:
            now = time.monotonic()
            if now - last_sweep >= _STALE_SWEEP_INTERVAL_SECONDS:
                requeued = repo.requeue_stale(config.stale_processing_seconds)
                for job_id in requeued:
                    publisher.publish(str(job_id), "queued")
                if requeued:
                    logger.warning("Requeued %d stale LLM job(s)", len(requeued))
                last_sweep = now

            job = repo.claim_next()
            if job is None:
                time.sleep(config.poll_interval_ms / 1000)
                continue

            job_id = str(job["id"])
            publisher.publish(job_id, "processing")

            prompt = (job.get("prompt") or "").strip()
            if not prompt:
                repo.mark_failed(job_id, "prompt is empty")
                publisher.publish(job_id, "failed")
                logger.warning("LLM job %s failed: empty prompt", job_id)
                continue

            logger.info("LLM job %s claimed", job_id)
            started = time.monotonic()
            try:
                response = client.chat(prompt)
            except NIMError as exc:
                message = str(exc)[:4000]
                repo.mark_failed(job_id, message)
                publisher.publish(job_id, "failed")
                logger.warning("LLM job %s failed: %s", job_id, message)
                continue
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"[:4000]
                repo.mark_failed(job_id, message)
                publisher.publish(job_id, "failed")
                logger.exception("LLM job %s failed unexpectedly", job_id)
                continue

            repo.mark_completed(job_id, response)
            publisher.publish(job_id, "completed")
            logger.info(
                "LLM job %s completed in %.1fs",
                job_id,
                time.monotonic() - started,
            )
    finally:
        client.close()
        redis_client.close()
        db.close()
        logger.info("LLM worker connection closed")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    run()
