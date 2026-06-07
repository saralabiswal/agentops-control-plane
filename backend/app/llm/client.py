from app.core.config import Settings
from app.llm.base import BaseLLMAdapter, LLMResponse, SupportsModelResolution
from app.llm.gemini import GeminiAdapter
from app.llm.groq import GroqAdapter
from app.llm.ollama import OllamaAdapter

__author__ = "Sarala Biswal"


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        """Register provider adapters from runtime configuration."""
        self.settings = settings
        self._adapters: dict[str, BaseLLMAdapter] = {
            "ollama": OllamaAdapter(host=settings.ollama_host),
        }
        if settings.groq_api_key:
            self._adapters["groq"] = GroqAdapter(api_key=settings.groq_api_key)
        if settings.gemini_api_key:
            self._adapters["gemini"] = GeminiAdapter(api_key=settings.gemini_api_key)

    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        """Route a completion request to the active provider using the resolved model name."""
        provider = self.settings.active_provider
        adapter = self._adapters.get(provider)
        if adapter is None:
            raise ValueError(f"Provider {provider!r} not configured")
        resolved_model = model or self.active_model()
        if isinstance(adapter, SupportsModelResolution):
            resolved_model = adapter.resolve_model(resolved_model)
        return await adapter.complete(prompt, resolved_model, max_tokens)

    def active_provider(self) -> str:
        return self.settings.active_provider

    def active_model(self) -> str:
        return self.settings.default_model_for(self.settings.active_provider)

    def available_providers(self) -> list[str]:
        return [name for name, adapter in self._adapters.items() if adapter.is_available()]
