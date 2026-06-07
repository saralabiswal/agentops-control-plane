import time

import httpx

from app.llm.base import LLMResponse, TokenUsage


class GroqAdapter:
    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def complete(self, prompt: str, model: str, max_tokens: int = 1000) -> LLMResponse:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
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

