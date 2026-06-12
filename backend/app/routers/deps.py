from typing import cast

from fastapi import Header, HTTPException, Request

from app.agents.registry import AgentRegistry
from app.core.config import Settings
from app.llm.client import LLMClient


def get_registry(request: Request) -> AgentRegistry:
    return cast(AgentRegistry, request.app.state.registry)


def get_llm(request: Request) -> LLMClient:
    return cast(LLMClient, request.app.state.llm)


def require_trace_access(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    settings = cast(Settings, request.app.state.settings)
    expected = settings.trace_api_key
    if not expected:
        return
    bearer = f"Bearer {expected}"
    if authorization == bearer or x_api_key == expected:
        return
    raise HTTPException(status_code=401, detail="Trace access requires a valid API key")
