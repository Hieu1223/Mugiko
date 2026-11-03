"""Environment-driven configuration for LLM Server."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.local", override=True)

DEFAULT_KEYS_FILE = "nim.txt"

def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default

def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default

@dataclass(frozen=True)
class LLMServerConfig:
    # Database
    database_url: str
    
    # Redis
    redis_url: str
    consumer_group: str = "llm-workers"
    consumer_name: str = "worker-1"
    input_stream: str = "conversation_messages"
    jobs_stream: str = "llm_jobs"
    output_stream: str = "llm_responses"
    read_block_ms: int = 5000
    claim_idle_ms: int = 300000
    stream_maxlen: int = 10000
    
    # NVIDIA NIM
    api_keys_file: str = "nim.txt"
    base_url: str = "https://integrate.api.nvidia.com/v1"
    model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    temperature: float = 0.2
    max_tokens: int = 4096
    timeout_seconds: float = 120.0
    
    # Processing
    poll_interval_ms: int = 2000
    max_concurrent_jobs: int = 10

    @classmethod
    def from_env(cls) -> "LLMServerConfig":
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL is required")
        
        return cls(
            database_url=database_url,
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            consumer_group=os.getenv("LLM_CONSUMER_GROUP", "llm-workers"),
            consumer_name=os.getenv("LLM_CONSUMER_NAME", "worker-1"),
            input_stream=os.getenv("LLM_INPUT_STREAM", "conversation_messages"),
            jobs_stream=os.getenv("LLM_JOBS_STREAM", "llm_jobs"),
            output_stream=os.getenv("LLM_OUTPUT_STREAM", "llm_responses"),
            read_block_ms=_env_int("LLM_READ_BLOCK_MS", 5000),
            claim_idle_ms=_env_int("LLM_CLAIM_IDLE_MS", 300000),
            stream_maxlen=_env_int("LLM_STREAM_MAXLEN", 10000),
            api_keys_file=os.getenv("NVIDIA_API_KEYS_FILE", DEFAULT_KEYS_FILE),
            base_url=os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/"),
            model=os.getenv("NVIDIA_NIM_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"),
            temperature=_env_float("NVIDIA_NIM_TEMPERATURE", 0.2),
            max_tokens=_env_int("NVIDIA_NIM_MAX_TOKENS", 4096),
            timeout_seconds=_env_float("NVIDIA_NIM_TIMEOUT_SECONDS", 120.0),
            poll_interval_ms=_env_int("LLM_POLL_INTERVAL_MS", 2000),
            max_concurrent_jobs=_env_int("LLM_MAX_CONCURRENT_JOBS", 10),
        )

    def load_api_keys(self) -> list[str]:
        try:
            with open(self.api_keys_file, "r", encoding="utf-8") as f:
                keys = [line.strip() for line in f if line.strip()]
        except OSError as exc:
            raise RuntimeError(f"Cannot read NVIDIA key file {self.api_keys_file!r}: {exc}") from exc
        if not keys:
            raise RuntimeError(f"NVIDIA key file {self.api_keys_file!r} contains no keys")
        return keys