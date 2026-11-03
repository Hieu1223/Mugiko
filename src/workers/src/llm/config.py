"""Environment-driven configuration for the LLM worker."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# The worker may be started directly through src.main; loading here keeps the
# module self-contained regardless of who owns the entrypoint.
load_dotenv()
load_dotenv(".env.local", override=True)

DEFAULT_KEYS_FILE = "nim.txt"
# Server-controlled model. Users never choose the model; this is the only one used.
MODEL = "nvidia/nemotron-3-ultra-550b-a55b"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default


@dataclass(frozen=True)
class LLMConfig:
    redis_url: str
    database_url: str
    api_keys_file: str
    base_url: str
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: float
    poll_interval_ms: int
    stale_processing_seconds: int
    status_stream: str
    status_stream_maxlen: int

    @classmethod
    def from_env(cls) -> "LLMConfig":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is required (PostgreSQL DSN). See .env.example."
            )
        return cls(
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            database_url=database_url,
            api_keys_file=os.getenv("NVIDIA_API_KEYS_FILE", DEFAULT_KEYS_FILE),
            base_url=os.getenv(
                "NVIDIA_NIM_BASE_URL",
                "https://integrate.api.nvidia.com/v1",
            ).rstrip("/"),
            model=MODEL,
            temperature=_env_float("NVIDIA_NIM_TEMPERATURE", 0.2),
            max_tokens=_env_int("NVIDIA_NIM_MAX_TOKENS", 4096),
            timeout_seconds=_env_float("NVIDIA_NIM_TIMEOUT_SECONDS", 120.0),
            poll_interval_ms=_env_int("LLM_POLL_INTERVAL_MS", 2000),
            stale_processing_seconds=_env_int(
                "LLM_STALE_PROCESSING_SECONDS",
                900,
            ),
            status_stream=os.getenv("LLM_STATUS_STREAM", "llm_status"),
            status_stream_maxlen=_env_int("LLM_STATUS_STREAM_MAXLEN", 10_000),
        )

    @classmethod
    def is_configured(cls) -> bool:
        """Return True when the configured key file exists and has a key."""
        path = os.getenv("NVIDIA_API_KEYS_FILE", DEFAULT_KEYS_FILE)
        try:
            with open(path, "r", encoding="utf-8") as keys_file:
                return any(line.strip() for line in keys_file)
        except OSError:
            return False

    def load_api_keys(self) -> list[str]:
        try:
            with open(self.api_keys_file, "r", encoding="utf-8") as keys_file:
                keys = [line.strip() for line in keys_file if line.strip()]
        except OSError as exc:
            raise RuntimeError(
                f"Cannot read NVIDIA key file {self.api_keys_file!r}: {exc}"
            ) from exc

        if not keys:
            raise RuntimeError(
                f"NVIDIA key file {self.api_keys_file!r} contains no keys"
            )
        return keys
