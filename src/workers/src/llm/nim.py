"""NVIDIA NIM OpenAI-compatible chat completions client.

Keys are read from a file by :class:`LLMConfig` and used round-robin, one key
per job. There is no environment-key fallback and no retry-on-failure logic.
"""

import logging
import time
from typing import Any, List

import requests

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 1.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class NIMError(RuntimeError):
    """A NIM request failed or returned an unusable response."""


def _extract_content(data: Any) -> str:
    try:
        message = data["choices"][0]["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise NIMError(
            f"Unexpected NIM response shape: {str(data)[:500]}"
        ) from exc

    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        content = "".join(parts)

    if not isinstance(content, str) or not content.strip():
        raise NIMError("NIM returned an empty response")

    return content


class NIMClient:
    """Small synchronous client for one NIM chat-completions endpoint."""

    def __init__(
        self,
        api_keys: List[str],
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float,
    ) -> None:
        if not api_keys:
            raise ValueError("api_keys must not be empty")

        self._api_keys = list(api_keys)
        self._next_key = 0
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds
        self._session = requests.Session()

    def _take_key(self) -> str:
        key = self._api_keys[self._next_key]
        self._next_key = (self._next_key + 1) % len(self._api_keys)
        return key

    def chat(self, prompt: str) -> str:
        key = self._take_key()
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": False,
        }

        last_error: NIMError | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = self._session.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    json=payload,
                    timeout=self._timeout,
                )
            except requests.RequestException as exc:
                last_error = NIMError(f"NIM request failed: {exc}")
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_RETRY_DELAY_SECONDS)
                    continue
                raise last_error from exc

            if response.status_code in _RETRYABLE_STATUS_CODES:
                body = " ".join(response.text.strip().split())
                last_error = NIMError(
                    f"NIM HTTP {response.status_code}: {body[:500]}"
                )
                if attempt < _MAX_ATTEMPTS:
                    time.sleep(_RETRY_DELAY_SECONDS)
                    continue
                raise last_error

            if response.status_code >= 400:
                body = " ".join(response.text.strip().split())
                raise NIMError(
                    f"NIM HTTP {response.status_code}: {body[:500]}"
                )

            try:
                data = response.json()
            except ValueError as exc:
                raise NIMError("NIM returned a non-JSON response") from exc

            return _extract_content(data)

        # Unreachable: the loop either returns or raises.
        raise last_error or NIMError("NIM request failed")

    def close(self) -> None:
        self._session.close()
