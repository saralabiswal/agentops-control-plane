from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.core.database import AsyncSessionLocal
from app.models.agent_run import AgentRun
from app.models.business_outcome import BusinessOutcome
from app.models.metric import Metric
from app.models.model_pricing import ModelPricing
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


class StaticLLM:
    def __init__(self, model: str) -> None:
        self.model = model

    def active_model(self) -> str:
        return self.model


def sprint_payload() -> dict[str, Any]:
    return {
        "sprint_name": "Orion",
        "team_size": 4,
        "days_remaining": 5,
        "total_tasks": 10,
        "completed_tasks": 4,
        "velocity_history": [8, 9, 7],
    }


def test_task_submission_uses_active_model_pricing(client) -> None:
    recorder = RecordingAgent()
    client.app.state.registry = RecordingRegistry(recorder)
    client.app.state.llm = StaticLLM("llama3.2:latest")
    session_id = client.post("/api/v1/sessions", json={"name": "Pricing Selection"}).json()["id"]

    response = client.post(
        "/api/v1/tasks",
        json={
            "agent_id": "agent-sprint-risk",
            "session_id": session_id,
            "input_payload": sprint_payload(),
            "priority": "HIGH",
        },
    )

    assert response.status_code == 200
    assert recorder.calls == [
        (response.json()["id"], "price-ollama-llama32-latest", None),
    ]


@pytest.mark.asyncio
async def test_retry_task_passes_prior_run_id_and_active_model_pricing(client) -> None:
    recorder = RecordingAgent()
    client.app.state.registry = RecordingRegistry(recorder)
    client.app.state.llm = StaticLLM("llama3.2:latest")
    session_id = client.post("/api/v1/sessions", json={"name": "Retry Routing"}).json()["id"]

    async with AsyncSessionLocal() as db:
        pricing = await db.get(ModelPricing, "price-ollama-llama32-latest")
        assert pricing is not None
        task = Task(
            session_id=session_id,
            agent_id="agent-sprint-risk",
            domain="PROJECT_DELIVERY",
            task_type="sprint_risk_assessment",
            input_payload=sprint_payload(),
        )
        db.add(task)
        await db.flush()
        db.add(
            AgentRun(
                id="prior-run",
                task_id=task.id,
                agent_id=task.agent_id,
                model_pricing_id=pricing.id,
                run_type="SINGLE_SHOT",
                model_used="llama3.2:latest",
                status="FAILED",
                raw_prompt="prompt",
                raw_response="{}",
                output_payload={},
            )
        )
        await db.commit()
        task_id = task.id

    response = client.post(f"/api/v1/tasks/{task_id}/retry")

    assert response.status_code == 200
    retry_task_id = response.json()["id"]
    assert retry_task_id != task_id
    assert recorder.calls == [(retry_task_id, "price-ollama-llama32-latest", "prior-run")]


def test_router_404s_are_explicit(client) -> None:
    missing_task = "00000000-0000-0000-0000-000000000000"
    session_id = client.post("/api/v1/sessions", json={"name": "Missing Routes"}).json()["id"]

    assert client.get("/api/v1/agents/not-an-agent").status_code == 404
    assert client.get(f"/api/v1/sessions/{missing_task}").status_code == 404
    assert client.get(f"/api/v1/tasks/{missing_task}").status_code == 404
    assert client.get(f"/api/v1/tasks/{missing_task}/status").status_code == 404
    assert client.post(f"/api/v1/tasks/{missing_task}/retry").status_code == 404
    assert client.get(f"/api/v1/runs/{missing_task}").status_code == 404
    assert client.get(f"/api/v1/runs/{missing_task}/quality").status_code == 404
    assert client.get(f"/api/v1/outcomes/{missing_task}").status_code == 404

    response = client.post(
        "/api/v1/tasks",
        json={
            "agent_id": "not-an-agent",
            "session_id": session_id,
            "input_payload": {},
            "priority": "NORMAL",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"


@pytest.mark.asyncio
async def test_run_filters_detail_children_and_quality_endpoint(client) -> None:
    base_ts = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    async with AsyncSessionLocal() as db:
        pricing = await db.get(ModelPricing, "price-ollama-llama32-3b")
        assert pricing is not None
        delivery_session = Session(name="Delivery Filters")
        revenue_session = Session(name="Revenue Filters")
        db.add_all([delivery_session, revenue_session])
        await db.flush()
        delivery_task = Task(
            session_id=delivery_session.id,
            agent_id="agent-project-planning",
            domain="PROJECT_DELIVERY",
            task_type="project_planning_workflow",
            input_payload={},
        )
        revenue_task = Task(
            session_id=revenue_session.id,
            agent_id="agent-renewal-risk",
            domain="REVENUE_OPS",
            task_type="renewal_risk_score",
            input_payload={},
        )
        db.add_all([delivery_task, revenue_task])
        await db.flush()
        parent = AgentRun(
            id="filter-parent",
            task_id=delivery_task.id,
            agent_id="agent-project-planning",
            model_pricing_id=pricing.id,
            run_type="WORKFLOW_PARENT",
            model_used="llama3.2:3b",
            status="COMPLETE",
            raw_prompt="plan",
            raw_response="{}",
            output_payload={"project_title": "Hardening"},
            quality_score=0.8,
            quality_relevance=0.9,
            quality_faithfulness=0.8,
            quality_completeness=0.7,
            quality_actionability=0.8,
            quality_dimensions={"reasoning_trace": "ok"},
            ran_at=base_ts,
        )
        child = AgentRun(
            id="filter-child",
            task_id=delivery_task.id,
            agent_id="node_decompose",
            model_pricing_id=pricing.id,
            run_type="WORKFLOW_NODE",
            parent_run_id=parent.id,
            model_used="llama3.2:3b",
            status="COMPLETE",
            raw_prompt="decompose",
            raw_response="{}",
            output_payload={"node": "decompose"},
            ran_at=base_ts + timedelta(minutes=1),
        )
        failed = AgentRun(
            id="filter-failed",
            task_id=revenue_task.id,
            agent_id="agent-renewal-risk",
            model_pricing_id=pricing.id,
            run_type="SINGLE_SHOT",
            model_used="llama3.2:3b",
            status="FAILED",
            error_message="provider unavailable",
            raw_prompt="renewal",
            raw_response="",
            output_payload={},
            ran_at=base_ts + timedelta(minutes=2),
        )
        db.add_all([parent, child, failed])
        await db.commit()
        delivery_session_id = delivery_session.id

    by_session = client.get("/api/v1/runs", params={"session_id": delivery_session_id}).json()
    by_domain = client.get("/api/v1/runs", params={"domain": "REVENUE_OPS"}).json()
    by_status = client.get("/api/v1/runs", params={"status": "FAILED"}).json()
    by_window = client.get(
        "/api/v1/runs",
        params={"from": (base_ts + timedelta(seconds=30)).isoformat()},
    ).json()
    detail = client.get("/api/v1/runs/filter-parent").json()
    quality = client.get("/api/v1/runs/filter-parent/quality").json()

    assert {run["id"] for run in by_session} == {"filter-parent", "filter-child"}
    assert [run["id"] for run in by_domain] == ["filter-failed"]
    assert [run["id"] for run in by_status] == ["filter-failed"]
    assert {run["id"] for run in by_window} == {"filter-child", "filter-failed"}
    assert [run["id"] for run in detail["child_runs"]] == ["filter-child"]
    assert quality["quality_score"] == 0.8
    assert quality["quality_dimensions"] == {"reasoning_trace": "ok"}


@pytest.mark.asyncio
async def test_session_metrics_and_outcome_aggregates(client) -> None:
    async with AsyncSessionLocal() as db:
        pricing = await db.get(ModelPricing, "price-ollama-llama32-3b")
        assert pricing is not None
        session = Session(name="Aggregate Test")
        db.add(session)
        await db.flush()
        complete_task = Task(
            session_id=session.id,
            agent_id="agent-sprint-risk",
            domain="PROJECT_DELIVERY",
            task_type="sprint_risk_assessment",
            input_payload=sprint_payload(),
        )
        failed_task = Task(
            session_id=session.id,
            agent_id="agent-renewal-risk",
            domain="REVENUE_OPS",
            task_type="renewal_risk_score",
            input_payload={},
        )
        db.add_all([complete_task, failed_task])
        await db.flush()
        complete_run = AgentRun(
            id="aggregate-complete",
            task_id=complete_task.id,
            agent_id=complete_task.agent_id,
            model_pricing_id=pricing.id,
            run_type="SINGLE_SHOT",
            model_used="llama3.2:3b",
            status="COMPLETE",
            latency_ms=100,
            cost_usd=2.0,
            quality_score=0.8,
            raw_prompt="prompt",
            raw_response="{}",
            output_payload={"risk_score": 0.4, "delivery_confidence_score": 0.7},
        )
        failed_run = AgentRun(
            id="aggregate-failed",
            task_id=failed_task.id,
            agent_id=failed_task.agent_id,
            model_pricing_id=pricing.id,
            run_type="SINGLE_SHOT",
            model_used="llama3.2:3b",
            status="FAILED",
            latency_ms=300,
            cost_usd=3.0,
            quality_score=0.4,
            raw_prompt="prompt",
            raw_response="{}",
            output_payload={},
        )
        db.add_all([complete_run, failed_run])
        await db.flush()
        db.add_all(
            [
                Metric(
                    agent_run_id=complete_run.id,
                    metric_name="cost_usd",
                    metric_value=2.0,
                    dimensions={"agent_id": complete_run.agent_id},
                ),
                Metric(
                    agent_run_id=failed_run.id,
                    metric_name="cost_usd",
                    metric_value=3.0,
                    dimensions={"agent_id": failed_run.agent_id},
                ),
                BusinessOutcome(
                    task_id=complete_task.id,
                    agent_run_id=complete_run.id,
                    domain="PROJECT_DELIVERY",
                    outcome_type="risk_mitigation",
                    metric_name="delivery_risk_mitigated_usd",
                    metric_value=20.0,
                    metric_unit="usd",
                    financial_impact_usd=20.0,
                    confidence_score=0.7,
                ),
            ]
        )
        await db.commit()
        session_id = session.id

    closed = client.post(f"/api/v1/sessions/{session_id}/close").json()
    cost_metrics = client.get("/api/v1/metrics/cost").json()
    quality_metrics = client.get("/api/v1/metrics/quality").json()
    latency_metrics = client.get("/api/v1/metrics/latency").json()
    throughput = client.get("/api/v1/metrics/throughput").json()
    session_outcomes = client.get(f"/api/v1/outcomes/session/{session_id}").json()
    summary = client.get("/api/v1/outcomes/summary").json()

    assert closed["status"] == "CLOSED"
    assert closed["total_tasks"] == 2
    assert closed["success_rate"] == 0.5
    assert closed["total_cost_usd"] == 5.0
    assert closed["avg_quality_score"] == pytest.approx(0.6)
    assert cost_metrics == [{"metric_name": "cost_usd", "value": 5.0}]
    assert {"agent_id": "agent-sprint-risk", "avg_quality_score": 0.8} in quality_metrics
    assert {"agent_id": "agent-renewal-risk", "avg_quality_score": 0.4} in quality_metrics
    assert {"agent_id": "agent-sprint-risk", "avg_latency_ms": 100.0, "max_latency_ms": 100} in (
        latency_metrics
    )
    assert throughput == {"total_runs": 2, "complete_runs": 1, "failed_runs": 1}
    assert session_outcomes["total_financial_impact_usd"] == 20.0
    assert len(session_outcomes["outcomes"]) == 1
    assert summary == {
        "total_financial_impact_usd": 20.0,
        "total_cost_usd": 5.0,
        "roi_multiple": 4.0,
    }
