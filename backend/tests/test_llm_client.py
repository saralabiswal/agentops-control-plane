from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.llm.base import LLMConfigurationError, LLMResponse, TokenUsage
from app.llm.client import LLMClient
from app.llm.gemini import GeminiAdapter
from app.llm.groq import GroqAdapter
from app.llm.ollama import OllamaAdapter


def test_settings_default_to_ollama_llama32_model() -> None:
    assert Settings.model_fields["active_provider"].default == "ollama"
    assert Settings.model_fields["ollama_model"].default == "llama3.2:3b"


class Adapter:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[tuple[str, str, int]] = []

    async def complete(self, prompt: str, model: str, max_tokens: int = 1000) -> LLMResponse:
        self.calls.append((prompt, model, max_tokens))
        return LLMResponse(
            text=f"{self.name}:{model}",
            usage=TokenUsage(prompt_tokens=3, completion_tokens=4, total_tokens=7),
            model=model,
            latency_ms=11,
        )

    def is_available(self) -> bool:
        return True


class ResolvingAdapter(Adapter):
    def resolve_model(self, model: str) -> str:
        if model == "llama3.2:3b":
            return "llama3.2:latest"
        return model


class RejectingAdapter(Adapter):
    def resolve_model(self, model: str) -> str:
        raise LLMConfigurationError(f"missing model: {model}")


class FakeAsyncClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []
        self.timeout: float | None = None

    def factory(self, timeout: float) -> "FakeAsyncClient":
        self.timeout = timeout
        return self

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        return httpx.Response(200, request=httpx.Request("POST", url), json=self.payload)


@pytest.mark.asyncio
async def test_llm_client_selects_active_provider_and_default_model() -> None:
    settings = Settings(active_provider="groq", groq_api_key="key")
    client = LLMClient(settings)
    adapter = Adapter("groq")
    client._adapters["groq"] = adapter

    response = await client.complete("hello")

    assert response.text == "groq:llama-3.3-70b-versatile"
    assert response.usage.total_tokens == 7
    assert adapter.calls == [("hello", "llama-3.3-70b-versatile", 1000)]


@pytest.mark.asyncio
async def test_llm_client_allows_per_call_model_override() -> None:
    settings = Settings(active_provider="ollama")
    client = LLMClient(settings)
    adapter = Adapter("ollama")
    client._adapters["ollama"] = adapter

    response = await client.complete("hello", model="custom", max_tokens=25)

    assert response.model == "custom"
    assert adapter.calls == [("hello", "custom", 25)]


@pytest.mark.asyncio
async def test_llm_client_resolves_provider_model_alias() -> None:
    settings = Settings(active_provider="ollama")
    client = LLMClient(settings)
    adapter = ResolvingAdapter("ollama")
    client._adapters["ollama"] = adapter

    response = await client.complete("hello")

    assert response.model == "llama3.2:latest"
    assert adapter.calls == [("hello", "llama3.2:latest", 1000)]


@pytest.mark.asyncio
async def test_llm_client_surfaces_model_configuration_errors() -> None:
    settings = Settings(active_provider="ollama")
    client = LLMClient(settings)
    client._adapters["ollama"] = RejectingAdapter("ollama")

    with pytest.raises(LLMConfigurationError, match="missing model"):
        await client.complete("hello")


def test_ollama_adapter_resolves_latest_tag_alias(monkeypatch) -> None:
    def fake_get(url: str, timeout: float) -> httpx.Response:
        assert url == "http://localhost:11434/api/tags"
        assert timeout == 2.0
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={
                "models": [
                    {
                        "name": "llama3.2:latest",
                        "capabilities": ["completion"],
                    },
                    {
                        "name": "nomic-embed-text:latest",
                        "capabilities": ["embedding"],
                    },
                ]
            },
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    assert OllamaAdapter().resolve_model("llama3.2:3b") == "llama3.2:latest"


@pytest.mark.asyncio
async def test_groq_adapter_posts_chat_completion_and_normalizes_response(monkeypatch) -> None:
    fake_client = FakeAsyncClient(
        {
            "model": "llama-3.3-70b-versatile",
            "choices": [{"message": {"content": "hello"}}],
            "usage": {
                "prompt_tokens": 5,
                "completion_tokens": 7,
                "total_tokens": 12,
            },
        }
    )
    monkeypatch.setattr(httpx, "AsyncClient", fake_client.factory)

    response = await GroqAdapter(api_key="secret").complete("prompt", "model-a", max_tokens=42)

    assert fake_client.timeout == 60.0
    assert fake_client.calls == [
        {
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "headers": {"Authorization": "Bearer secret"},
            "json": {
                "model": "model-a",
                "messages": [{"role": "user", "content": "prompt"}],
                "max_tokens": 42,
            },
        }
    ]
    assert response.text == "hello"
    assert response.model == "llama-3.3-70b-versatile"
    assert response.usage.total_tokens == 12


@pytest.mark.asyncio
async def test_gemini_adapter_posts_generate_content_and_normalizes_response(monkeypatch) -> None:
    fake_client = FakeAsyncClient(
        {
            "candidates": [{"content": {"parts": [{"text": "gemini text"}]}}],
            "usageMetadata": {
                "promptTokenCount": 3,
                "candidatesTokenCount": 4,
                "totalTokenCount": 7,
            },
        }
    )
    monkeypatch.setattr(httpx, "AsyncClient", fake_client.factory)

    response = await GeminiAdapter(api_key="key").complete("prompt", "gemini-2.0-flash", 33)

    assert fake_client.timeout == 60.0
    assert fake_client.calls == [
        {
            "url": "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.0-flash:generateContent",
            "params": {"key": "key"},
            "json": {
                "contents": [{"parts": [{"text": "prompt"}]}],
                "generationConfig": {"maxOutputTokens": 33},
            },
        }
    ]
    assert response.text == "gemini text"
    assert response.model == "gemini-2.0-flash"
    assert response.usage.total_tokens == 7


@pytest.mark.asyncio
async def test_llm_client_rejects_unconfigured_provider() -> None:
    client = LLMClient(Settings(active_provider="gemini", gemini_api_key=""))

    with pytest.raises(ValueError, match="not configured"):
        await client.complete("hello")
