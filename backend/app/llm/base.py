from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class LLMConfigurationError(RuntimeError):
    """Raised when the selected provider/model cannot be used."""


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class LLMResponse:
    text: str
    usage: TokenUsage
    model: str
    latency_ms: int


@runtime_checkable
class BaseLLMAdapter(Protocol):
    async def complete(self, prompt: str, model: str, max_tokens: int = 1000) -> LLMResponse:
        ...

    def is_available(self) -> bool:
        ...


@runtime_checkable
class SupportsClose(Protocol):
    async def aclose(self) -> None:
        ...


@runtime_checkable
class SupportsModelResolution(Protocol):
    def resolve_model(self, model: str) -> str:
        ...
