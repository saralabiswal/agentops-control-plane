import time
from typing import Any

import httpx

from app.llm.base import LLMResponse, TokenUsage


class GroqAdapter:
    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        api_key: str,
        http_client: httpx.AsyncClient | None = None,
        *,
        timeout: float = 60.0,
        max_retries: int = 1,
    ) -> None:
        self.api_key = api_key
        self._client = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = http_client is None
        self.max_retries = max_retries

    async def complete(self, prompt: str, model: str, max_tokens: int = 1000) -> LLMResponse:
        start = time.monotonic()
        resp = await self._post_with_retries(
            f"{self.BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
        )
        data = resp.json()
        usage = data["usage"]
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            usage=TokenUsage(
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                total_tokens=usage["total_tokens"],
            ),
            model=data.get("model", model),
            latency_ms=int((time.monotonic() - start) * 1000),
        )

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _post_with_retries(self, url: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.post(url, **kwargs)
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
                if attempt >= self.max_retries or not _is_transient(exc):
                    raise
        raise RuntimeError("unreachable retry state")


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (httpx.TimeoutException, httpx.RequestError))
