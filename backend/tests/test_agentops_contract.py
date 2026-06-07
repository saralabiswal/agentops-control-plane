import pytest
from sqlalchemy import func, select

from app.agentops.manager import recover_stale_runs
from app.core.database import AsyncSessionLocal
from app.core.enums import RunStatus
from app.llm.base import LLMConfigurationError
from app.models.agent_run import AgentRun
from app.models.metric import Metric
from app.models.model_pricing import ModelPricing


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
