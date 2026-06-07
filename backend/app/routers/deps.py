from typing import cast

from fastapi import Request

from app.agents.registry import AgentRegistry
from app.llm.client import LLMClient


def get_registry(request: Request) -> AgentRegistry:
    return cast(AgentRegistry, request.app.state.registry)


def get_llm(request: Request) -> LLMClient:
    return cast(LLMClient, request.app.state.llm)
