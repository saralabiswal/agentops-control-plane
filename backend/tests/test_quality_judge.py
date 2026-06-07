from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.agentops.context import RunContext
from app.agentops.quality_queue import QualityQueue
from app.agentops.sse_emitter import SSEEmitter
from app.agents.platform.quality_judge import QualityJudgeAgent
from app.core.database import AsyncSessionLocal
from app.core.enums import RunType
from app.models.agent_run import AgentRun
from app.models.metric import Metric
from tests.conftest import FakeLLM, llm_response


def context() -> RunContext:
    return RunContext(
        run_id="run-1",
        task_id="task-1",
        agent_id="agent-sprint-risk",
        session_id="session-1",
        started_at=datetime.now(UTC),
        model_used="llama3.2:3b",
        model_pricing_id="price-ollama-llama32-3b",
        run_type=RunType.SINGLE_SHOT,
        raw_prompt="Sprint Orion with 5 days left",
        raw_response='{"risk_score":0.7}',
        output_payload={"risk_score": 0.7},
    )


@pytest.mark.asyncio
async def test_quality_judge_scores_dimensions_and_loads_rubric() -> None:
    llm = FakeLLM(
        [
            llm_response(
                '{"relevance":0.8,"faithfulness":0.9,"completeness":0.7,'
                '"actionability":0.6,"reasoning_trace":"Good sprint grounding."}'
            )
        ]
    )
    judge = QualityJudgeAgent(llm)

    scores = await judge.score(context())

    assert scores["quality_score"] == pytest.approx(0.75)
    assert scores["quality_relevance"] == 0.8
    assert "sprint" in llm.prompts[0].lower()
    assert scores["quality_dimensions"]["reasoning_trace"] == "Good sprint grounding."


@pytest.mark.asyncio
async def test_quality_judge_handles_bad_json_gracefully() -> None:
    judge = QualityJudgeAgent(FakeLLM([llm_response("not-json")]))

    scores = await judge.score(context())

    assert scores["quality_score"] == 0.0
    assert "Judge failed" in scores["quality_dimensions"]["reasoning_trace"]


@pytest.mark.asyncio
async def test_quality_queue_worker_updates_run_and_emits_sse(session_task) -> None:
    session, task, agent, pricing = session_task
    ctx = context()
    ctx.run_id = "quality-run"
    ctx.task_id = task.id
    ctx.agent_id = agent.id
    ctx.session_id = session.id
    ctx.model_pricing_id = pricing.id
    emitter = SSEEmitter()
    queue = QualityQueue(emitter)
    subscriber = emitter.subscribe("quality-sub")

    async with AsyncSessionLocal() as db:
        db.add(
            AgentRun(
                id=ctx.run_id,
                task_id=ctx.task_id,
                agent_id=ctx.agent_id,
                model_pricing_id=ctx.model_pricing_id,
                run_type="SINGLE_SHOT",
                model_used=ctx.model_used,
                status="COMPLETE",
                raw_prompt=ctx.raw_prompt,
                raw_response=ctx.raw_response,
                output_payload=ctx.output_payload,
            )
        )
        await db.commit()

    judge = QualityJudgeAgent(
        FakeLLM(
            [
                llm_response(
                    '{"relevance":1,"faithfulness":1,"completeness":0.8,'
                    '"actionability":0.8,"reasoning_trace":"Useful."}'
                )
            ]
        )
    )
    await queue.enqueue(ctx)
    await queue.worker(judge, stop_when_empty=True)

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, ctx.run_id)
        quality_metric = await db.scalar(
            select(Metric).where(
                Metric.agent_run_id == ctx.run_id,
                Metric.metric_name == "quality_score",
            )
        )

    event = await subscriber.get()
    assert run is not None
    assert run.quality_score == 0.9
    assert quality_metric is not None
    assert "quality_scored" in event
