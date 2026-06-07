import time

import httpx

from app.llm.base import LLMConfigurationError, LLMResponse, TokenUsage


class OllamaAdapter:
    def __init__(self, host: str = "http://localhost:11434") -> None:
        self.host = host.rstrip("/")

    async def complete(self, prompt: str, model: str, max_tokens: int = 1000) -> LLMResponse:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.host}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
            )
            resp.raise_for_status()
        data = resp.json()
        prompt_tokens = int(data.get("prompt_eval_count", 0))
        completion_tokens = int(data.get("eval_count", 0))
        return LLMResponse(
            text=data["response"],
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            model=data.get("model", model),
            latency_ms=int((time.monotonic() - start) * 1000),
        )

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self.host}/api/tags", timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    def available_models(self) -> list[str]:
        try:
            resp = httpx.get(f"{self.host}/api/tags", timeout=2.0)
            resp.raise_for_status()
        except httpx.RequestError as exc:
            raise LLMConfigurationError(
                f"Ollama is not reachable at {self.host}. Start Ollama or configure "
                "AGENTOPS_ACTIVE_PROVIDER with an available provider."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMConfigurationError(
                f"Ollama model catalog request failed with HTTP {exc.response.status_code}."
            ) from exc

        models = resp.json().get("models", [])
        names: list[str] = []
        for model in models:
            capabilities = model.get("capabilities", [])
            name = model.get("name") or model.get("model")
            if isinstance(name, str) and (not capabilities or "completion" in capabilities):
                names.append(name)
        return names

    def resolve_model(self, model: str) -> str:
        available = self.available_models()
        if model in available:
            return model

        model_family = model.split(":", maxsplit=1)[0]
        latest_alias = f"{model_family}:latest"
        if latest_alias in available:
            return latest_alias

        family_matches = sorted(name for name in available if name.startswith(f"{model_family}:"))
        if len(family_matches) == 1:
            return family_matches[0]

        installed = ", ".join(available) if available else "none"
        raise LLMConfigurationError(
            f"Ollama model {model!r} is not installed. Installed completion models: "
            f"{installed}. Run `ollama pull {model}` or set AGENTOPS_OLLAMA_MODEL "
            "to an installed model."
        )
