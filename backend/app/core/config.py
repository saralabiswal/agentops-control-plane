from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    active_provider: str = "ollama"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    quality_judge_model: str = "llama3.1:8b"

    max_concurrent_agents: int = 6
    llm_timeout_seconds: int = 30
    sse_heartbeat_seconds: int = 15
    auto_retry_on_failure: bool = True
    async_quality_scoring: bool = True

    database_url: str = "sqlite+aiosqlite:///./agentops.db"
    trace_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AGENTOPS_")

    def default_model_for(self, provider: str) -> str:
        return {
            "ollama": self.ollama_model,
            "groq": self.groq_model,
            "gemini": self.gemini_model,
        }[provider]


@lru_cache
def get_settings() -> Settings:
    return Settings()
