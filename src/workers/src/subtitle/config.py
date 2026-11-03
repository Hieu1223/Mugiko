"""Environment-driven configuration for the subtitle worker."""

import getpass
import os
from dataclasses import dataclass

from dotenv import load_dotenv

# The worker may be started directly through src.main; loading here keeps the
# module self-contained regardless of who owns the entrypoint.
load_dotenv()
load_dotenv(".env.local", override=True)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


@dataclass(frozen=True)
class SubtitleConfig:
    redis_url: str
    database_url: str
    consumer_group: str
    consumer_name: str
    read_block_ms: int
    claim_idle_ms: int
    status_stream: str
    status_stream_maxlen: int

    @classmethod
    def from_env(cls) -> "SubtitleConfig":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is required (PostgreSQL DSN). See .env.example."
            )
        return cls(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            database_url=database_url,
            consumer_group=os.getenv("CONSUMER_GROUP", "subtitle-workers"),
            consumer_name=os.getenv(
                "CONSUMER_NAME",
                f"worker-{getpass.getuser()}-{os.getpid()}",
            ),
            read_block_ms=_env_int("READ_BLOCK_MS", 5000),
            claim_idle_ms=_env_int("CLAIM_IDLE_MS", 300_000),
            status_stream=os.getenv("STATUS_STREAM", "subtitle_status"),
            status_stream_maxlen=_env_int("STATUS_STREAM_MAXLEN", 10_000),
        )
