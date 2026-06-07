import time

import httpx

from app.llm.base import LLMResponse, TokenUsage


class GeminiAdapter:
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def complete(self, prompt: str, model: str, max_tokens: int = 1000) -> LLMResponse:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/models/{model}:generateContent",
                params={"key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": max_tokens},
                },
            )
            resp.raise_for_status()
        data = resp.json()
        metadata = data.get("usageMetadata", {})
        return LLMResponse(
            text=data["candidates"][0]["content"]["parts"][0]["text"],
            usage=TokenUsage(
                prompt_tokens=metadata.get("promptTokenCount", 0),
                completion_tokens=metadata.get("candidatesTokenCount", 0),
                total_tokens=metadata.get("totalTokenCount", 0),
            ),
            model=model,
            latency_ms=int((time.monotonic() - start) * 1000),
        )

    def is_available(self) -> bool:
        return bool(self.api_key)

