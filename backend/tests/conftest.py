from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.agentops.cost_calculator import CostCalculator
from app.agentops.manager import AgentOpsManager
from app.agentops.quality_queue import QualityQueue
from app.agentops.sse_emitter import SSEEmitter
from app.core.database import AsyncSessionLocal, engine
from app.llm.base import LLMResponse, TokenUsage
from app.models import Base
from app.models.agent_definition import AgentDefinition
from app.models.model_pricing import ModelPricing
from app.models.session import Session
from app.models.task import Task
from app.seed.seed import run_seed


@pytest_asyncio.fixture(autouse=True)
async def clean_db() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await run_seed()
    yield


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@dataclass
class FakeLLM:
    responses: list[LLMResponse]
    provider: str = "ollama"
    model: str = "llama3.2:3b"

    def __post_init__(self) -> None:
        self.settings = type("Settings", (), {"quality_judge_model": "llama3.1:8b"})()
        self.prompts: list[str] = []

    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        self.prompts.append(prompt)
        if not self.responses:
            return llm_response("{}")
        return self.responses.pop(0)

    def active_provider(self) -> str:
        return self.provider

    def active_model(self) -> str:
        return self.model

    def available_providers(self) -> list[str]:
        return [self.provider]


def llm_response(
    text: str,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    model: str = "llama3.2:3b",
) -> LLMResponse:
    return LLMResponse(
        text=text,
        usage=TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
        model=model,
        latency_ms=12,
    )


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator:
    async with AsyncSessionLocal() as db:
        yield db


@pytest_asyncio.fixture
async def session_task(db_session) -> tuple[Session, Task, AgentDefinition, ModelPricing]:
    session = Session(name="Test Session")
    agent = await db_session.get(AgentDefinition, "agent-sprint-risk")
    pricing = await db_session.get(ModelPricing, "price-ollama-llama32-3b")
    assert agent is not None
    assert pricing is not None
    task = Task(
        session=session,
        agent_id=agent.id,
        domain=agent.domain,
        task_type=agent.agent_type,
        input_payload={
            "sprint_name": "Orion",
            "team_size": 4,
            "days_remaining": 5,
            "total_tasks": 10,
            "completed_tasks": 4,
            "velocity_history": [8, 9, 7],
            "delay_cost_per_week_usd": 100000,
        },
    )
    db_session.add_all([session, task])
    await db_session.commit()
    await db_session.refresh(session)
    await db_session.refresh(task)
    return session, task, agent, pricing


@pytest.fixture
def agentops() -> AgentOpsManager:
    sse = SSEEmitter()
    quality = QualityQueue(sse)
    return AgentOpsManager(sse, quality, CostCalculator())
