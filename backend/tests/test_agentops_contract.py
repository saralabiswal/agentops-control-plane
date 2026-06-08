from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.agentops.context import RunContext
from app.agentops.cost_calculator import (
    API_CALLS_PER_AGENT_RUN,
    COMPUTE_MEMORY_GIB_PER_AGENT_RUN,
    COMPUTE_VCPU_PER_AGENT_RUN,
    CostCalculator,
)
from app.agentops.manager import AgentOpsManager, recover_stale_runs
from app.agentops.quality_queue import QualityQueue
from app.agentops.sse_emitter import SSEEmitter
from app.core.database import AsyncSessionLocal
from app.core.enums import RunStatus, RunType, TaskStatus
from app.llm.base import LLMConfigurationError
from app.models.agent_run import AgentRun
from app.models.metric import Metric
from app.models.model_pricing import ModelPricing
from app.models.task import Task


class FailingOutcomeWriter:
    async def write_for_run(self, db, ctx) -> None:
        raise TypeError("bad outcome payload")


@pytest.mark.asyncio
async def test_running_record_written_before_yield(agentops, session_task) -> None:
    session, task, agent, pricing = session_task

    async with agentops.run_context(
        task_id=task.id,
        agent_id=agent.id,
        session_id=session.id,
        model_used="llama3.2:3b",
        model_pricing_id=pricing.id,
    ) as ctx:
        async with AsyncSessionLocal() as db:
            run = await db.get(AgentRun, ctx.run_id)
        assert run is not None
        assert run.status == RunStatus.RUNNING


@pytest.mark.asyncio
async def test_finally_runs_on_success_and_writes_metrics(agentops, session_task) -> None:
    session, task, agent, pricing = session_task

    async with agentops.run_context(
        task_id=task.id,
        agent_id=agent.id,
        session_id=session.id,
        model_used="llama3.2:3b",
        model_pricing_id=pricing.id,
    ) as ctx:
        ctx.raw_prompt = "prompt"
        ctx.raw_response = '{"risk_score":0.5}'
        ctx.prompt_tokens = 10
        ctx.completion_tokens = 5
        ctx.output_payload = {"risk_score": 0.5, "delivery_confidence_score": 0.7}

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, ctx.run_id)
        metric_count = await db.scalar(
            select(func.count(Metric.id)).where(Metric.agent_run_id == ctx.run_id)
        )

    assert run is not None
    assert run.status == RunStatus.COMPLETE
    assert run.total_tokens == 15
    assert metric_count == 4
    assert agentops.quality.queue.qsize() == 1


@pytest.mark.asyncio
async def test_outcome_write_failure_marks_run_and_task_failed(session_task) -> None:
    session, task, agent, pricing = session_task
    sse = SSEEmitter()
    manager = AgentOpsManager(
        sse,
        QualityQueue(sse),
        CostCalculator(),
        outcome_calculator=FailingOutcomeWriter(),
    )

    async with manager.run_context(
        task_id=task.id,
        agent_id=agent.id,
        session_id=session.id,
        model_used="llama3.2:3b",
        model_pricing_id=pricing.id,
    ) as ctx:
        ctx.output_payload = {"risk_score": 0.25}

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, ctx.run_id)
        persisted_task = await db.get(Task, task.id)

    assert run is not None
    assert run.status == RunStatus.FAILED
    assert run.error_message is not None
    assert "Outcome calculation failed" in run.error_message
    assert persisted_task is not None
    assert persisted_task.status == TaskStatus.FAILED
    assert manager.quality.queue.qsize() == 0


@pytest.mark.asyncio
async def test_failed_run_does_not_enqueue_quality(agentops, session_task) -> None:
    session, task, agent, pricing = session_task

    async with agentops.run_context(
        task_id=task.id,
        agent_id=agent.id,
        session_id=session.id,
        model_used="llama3.2:3b",
        model_pricing_id=pricing.id,
    ):
        raise ValueError("bad json")

    async with AsyncSessionLocal() as db:
        run = await db.scalar(select(AgentRun).where(AgentRun.task_id == task.id))

    assert run is not None
    assert run.status == RunStatus.FAILED
    assert "Output parse failed" in (run.error_message or "")
    assert agentops.quality.queue.qsize() == 0


@pytest.mark.asyncio
async def test_llm_configuration_error_is_recorded_without_reraise(agentops, session_task) -> None:
    session, task, agent, pricing = session_task

    async with agentops.run_context(
        task_id=task.id,
        agent_id=agent.id,
        session_id=session.id,
        model_used="llama3.2:3b",
        model_pricing_id=pricing.id,
    ):
        raise LLMConfigurationError("Ollama model missing")

    async with AsyncSessionLocal() as db:
        run = await db.scalar(select(AgentRun).where(AgentRun.task_id == task.id))

    assert run is not None
    assert run.status == RunStatus.FAILED
    assert run.error_message == "LLM configuration error: Ollama model missing"


@pytest.mark.asyncio
async def test_unknown_exception_reraised_after_recording(agentops, session_task) -> None:
    session, task, agent, pricing = session_task

    with pytest.raises(RuntimeError, match="Unexpected error"):
        async with agentops.run_context(
            task_id=task.id,
            agent_id=agent.id,
            session_id=session.id,
            model_used="llama3.2:3b",
            model_pricing_id=pricing.id,
        ):
            raise RuntimeError("boom")

    async with AsyncSessionLocal() as db:
        run = await db.scalar(select(AgentRun).where(AgentRun.task_id == task.id))
    assert run is not None
    assert run.status == RunStatus.FAILED


@pytest.mark.asyncio
async def test_cost_calculated_from_locked_pricing(agentops, session_task, db_session) -> None:
    session, task, agent, _pricing = session_task
    pricing = ModelPricing(
        id="price-test",
        provider="groq",
        model_name="priced-model",
        input_cost_per_1k=1.0,
        output_cost_per_1k=2.0,
    )
    db_session.add(pricing)
    await db_session.commit()

    async with agentops.run_context(
        task_id=task.id,
        agent_id=agent.id,
        session_id=session.id,
        model_used="priced-model",
        model_pricing_id=pricing.id,
    ) as ctx:
        ctx.prompt_tokens = 1000
        ctx.completion_tokens = 500
        ctx.output_payload = {"risk_score": 0.1}

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, ctx.run_id)
    assert run is not None
    assert run.cost_usd == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_cost_calculator_includes_api_calls_and_compute(db_session) -> None:
    pricing = ModelPricing(
        id="price-operational",
        provider="ollama",
        model_name="priced-model",
        input_cost_per_1k=1.0,
        output_cost_per_1k=2.0,
        api_call_cost_per_1k=10.0,
        compute_vcpu_cost_per_second=0.5,
        compute_memory_gib_cost_per_second=0.25,
    )
    db_session.add(pricing)
    await db_session.commit()

    ctx = RunContext(
        run_id="run-operational",
        task_id="task-operational",
        agent_id="agent-sprint-risk",
        session_id="session-operational",
        started_at=datetime.now(UTC),
        model_used="priced-model",
        model_pricing_id=pricing.id,
        run_type=RunType.SINGLE_SHOT,
        prompt_tokens=1000,
        completion_tokens=500,
        latency_ms=2000,
    )

    cost = await CostCalculator().calculate(db_session, ctx)
    expected_token_cost = 2.0
    expected_api_cost = API_CALLS_PER_AGENT_RUN / 1000 * pricing.api_call_cost_per_1k
    expected_compute_cost = 2.0 * (
        COMPUTE_VCPU_PER_AGENT_RUN * pricing.compute_vcpu_cost_per_second
        + COMPUTE_MEMORY_GIB_PER_AGENT_RUN * pricing.compute_memory_gib_cost_per_second
    )

    assert cost == pytest.approx(
        expected_token_cost + expected_api_cost + expected_compute_cost
    )


@pytest.mark.asyncio
async def test_stored_cost_is_not_recomputed_when_pricing_changes(
    agentops, session_task, db_session
) -> None:
    session, task, agent, _pricing = session_task
    pricing = ModelPricing(
        id="price-immutable",
        provider="groq",
        model_name="priced-model",
        input_cost_per_1k=1.0,
        output_cost_per_1k=1.0,
    )
    db_session.add(pricing)
    await db_session.commit()

    async with agentops.run_context(
        task_id=task.id,
        agent_id=agent.id,
        session_id=session.id,
        model_used="priced-model",
        model_pricing_id=pricing.id,
    ) as ctx:
        ctx.prompt_tokens = 1000
        ctx.output_payload = {"risk_score": 0.1}

    pricing.input_cost_per_1k = 100.0
    await db_session.commit()

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, ctx.run_id)

    assert run is not None
    assert run.cost_usd == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_sse_emitted_on_start_and_complete(agentops, session_task) -> None:
    session, task, agent, pricing = session_task
    queue = agentops.sse.subscribe("test")

    async with agentops.run_context(
        task_id=task.id,
        agent_id=agent.id,
        session_id=session.id,
        model_used="llama3.2:3b",
        model_pricing_id=pricing.id,
    ) as ctx:
        ctx.output_payload = {"risk_score": 0.1}

    started = await queue.get()
    completed = await queue.get()

    assert "run_started" in started
    assert "run_completed" in completed


@pytest.mark.asyncio
async def test_stale_running_recovery(session_task, db_session) -> None:
    session, task, agent, pricing = session_task
    run = AgentRun(
        id="stale-run",
        task_id=task.id,
        agent_id=agent.id,
        model_pricing_id=pricing.id,
        run_type="SINGLE_SHOT",
        model_used="llama3.2:3b",
        status=RunStatus.RUNNING,
        raw_prompt="",
        raw_response="",
        output_payload={},
    )
    db_session.add(run)
    await db_session.commit()

    await recover_stale_runs()

    async with AsyncSessionLocal() as db:
        recovered = await db.get(AgentRun, "stale-run")
    assert recovered is not None
    assert recovered.status == RunStatus.FAILED


@pytest.mark.asyncio
async def test_retry_of_is_recorded_on_retry_runs(agentops, session_task) -> None:
    session, task, agent, pricing = session_task

    async with agentops.run_context(
        task_id=task.id,
        agent_id=agent.id,
        session_id=session.id,
        model_used="llama3.2:3b",
        model_pricing_id=pricing.id,
        retry_of="original-run",
    ) as ctx:
        ctx.output_payload = {"risk_score": 0.1}

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, ctx.run_id)

    assert run is not None
    assert run.retry_of == "original-run"
