import pytest

from app.agentops.task_queue import TaskWorker, recover_stale_tasks
from app.core.database import AsyncSessionLocal
from app.core.enums import TaskStatus
from app.models.session import Session
from app.models.task import Task


class RecordingAgent:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    async def run(self, task: Task, model_pricing_id: str, retry_of: str | None = None) -> None:
        self.calls.append((task.id, model_pricing_id, retry_of))


class RecordingRegistry:
    def __init__(self, agent: RecordingAgent) -> None:
        self.agent = agent

    def get(self, agent_id: str) -> RecordingAgent:
        return self.agent


@pytest.mark.asyncio
async def test_task_worker_uses_persisted_pricing_and_retry_metadata() -> None:
    agent = RecordingAgent()
    worker = TaskWorker(lambda: RecordingRegistry(agent), max_concurrent_tasks=1)

    async with AsyncSessionLocal() as db:
        session = Session(name="Queue Metadata")
        db.add(session)
        await db.flush()
        task = Task(
            session_id=session.id,
            agent_id="agent-sprint-risk",
            domain="PROJECT_DELIVERY",
            task_type="sprint_risk_assessment",
            input_payload={},
            model_pricing_id="price-ollama-llama32-3b",
            retry_of_run_id="prior-run",
        )
        db.add(task)
        await db.commit()
        task_id = task.id

    processed = await worker.run_until_idle()

    async with AsyncSessionLocal() as db:
        task = await db.get(Task, task_id)

    assert processed == 1
    assert agent.calls == [(task_id, "price-ollama-llama32-3b", "prior-run")]
    assert task is not None
    assert task.status == TaskStatus.RUNNING
    assert task.attempt_count == 1
    assert task.claimed_at is not None


@pytest.mark.asyncio
async def test_recover_stale_tasks_requeues_claim_without_run_record() -> None:
    async with AsyncSessionLocal() as db:
        session = Session(name="Queue Recovery")
        db.add(session)
        await db.flush()
        task = Task(
            session_id=session.id,
            agent_id="agent-sprint-risk",
            domain="PROJECT_DELIVERY",
            task_type="sprint_risk_assessment",
            input_payload={},
            status=TaskStatus.RUNNING,
            model_pricing_id="price-ollama-llama32-3b",
        )
        db.add(task)
        await db.commit()
        task_id = task.id

    await recover_stale_tasks()

    async with AsyncSessionLocal() as db:
        task = await db.get(Task, task_id)

    assert task is not None
    assert task.status == TaskStatus.QUEUED
    assert task.started_at is None
    assert task.claimed_at is None
    assert task.last_error == "Recovered interrupted task claim on startup"
