"""Local Ollama LLM client for real quantized narrative synthesis and explainability."""

import time
from typing import Any

import httpx

from packages.shared.logger import logger


class OllamaClient:
    """Interacts with local Ollama daemon at http://localhost:11434 with zero network costs."""

    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "qwen3:4b"

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.last_used_fallback: bool = False

    def is_available(self) -> bool:
        """Checks if local Ollama daemon is reachable and responding."""
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def generate_narrative(
        self,
        prompt: str,
        max_tokens: int = 60,
    ) -> tuple[str, float, int]:
        """Generates real local quantized completion.

        Returns: (response_text, latency_ms, token_count)
        """
        start = time.perf_counter()
        url = f"{self.base_url}/api/generate"
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.1,
            },
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    response_text = data.get("response", "").strip()
                    eval_count = data.get("eval_count", len(response_text) // 4)
                    latency_ms = (time.perf_counter() - start) * 1000.0
                    self.last_used_fallback = False
                    return response_text, latency_ms, eval_count
        except Exception as exc:
            logger.debug("ollama_local_fallback", error=str(exc))

        # Deterministic offline fallback if daemon is restarting or unavailable
        self.last_used_fallback = True
        latency_ms = (time.perf_counter() - start) * 1000.0
        fallback_text = f"ChangeScope deterministic analysis: evaluated impact for '{prompt[:40]}...'."
        return fallback_text, latency_ms, len(fallback_text) // 4
